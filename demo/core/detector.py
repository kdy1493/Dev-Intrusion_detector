import cv2
import time
import threading
import requests
import numpy as np
import paho.mqtt.client as paho
from typing import Optional, Tuple
from ultralytics import YOLO
from sam2.build_sam import build_sam2_object_tracker
from demo.config.settings import (
    YOLO_MODEL_PATH, DEVICE, SAM_CONFIG_PATH, SAM_CHECKPOINT_PATH, 
    MASK_THRESHOLD, DEMO_API, BROKER_ADDR, BROKER_PORT
)
from demo.utils.alerts import AlertManager, AlertCodes
import torch

class HumanDetector:
    def __init__(self):
        self.model = YOLO(YOLO_MODEL_PATH)
        self._warm_up()

    def _warm_up(self):
        dummy = torch.zeros(1, 3, 640, 640, device=DEVICE)
        _ = self.model.predict(dummy, device=DEVICE, verbose=False) 
    
    def detect(self, frame):
        persons = []
        results = self.model.predict(frame, classes=[0], device=DEVICE, verbose=False)
        max_conf = 0
        best_box = None
        
        for res in results:
            for box in res.boxes:
                conf = float(box.conf[0])
                if conf > max_conf:
                    max_conf = conf
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    best_box = [[x1, y1], [x2, y2]]
        
        if best_box is not None:
            persons.append(best_box)
        
        return persons


class HumanTracker:
    def __init__(self):
        self.tracker = build_sam2_object_tracker(
            num_objects=1,
            config_file=SAM_CONFIG_PATH,
            ckpt_path=SAM_CHECKPOINT_PATH,
            device=DEVICE,
            verbose=False
        )
        self._warm_up()
        self.last_center = None
        self.stationary_timer_start = None

    def _warm_up(self):
        dummy = np.zeros((256, 256, 3), np.uint8)
        _ = self.tracker.track_all_objects(img=dummy)

    def initialize(self, frame, persons):
        self.tracker.track_new_object(
            img=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
            box=np.array(persons)
        )
    
    def track(self, frame):
        if self.tracker is None:
            return None, False
            
        out = self.tracker.track_all_objects(img=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        masks = out.get("pred_masks")
        has_mask = False
        
        if masks is not None:
            m_np = masks.cpu().numpy()
            for i in range(m_np.shape[0]):
                if (m_np[i,0] > MASK_THRESHOLD).sum() > 0:
                    has_mask = True
                    break
                    
        return m_np if has_mask else None, has_mask
    
    def check_stationary(self, bbox_coords, current_time):
        if bbox_coords is None:
            return False
            
        x1, y1, x2, y2 = bbox_coords
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        
        if self.last_center is None:
            self.last_center = (cx, cy)
            self.stationary_timer_start = current_time
            return False
            
        dist = np.hypot(cx - self.last_center[0], cy - self.last_center[1])
        
        if dist < 5:
            if self.stationary_timer_start and current_time - self.stationary_timer_start >= 3.0:
                self.stationary_timer_start = None
                return True
        else:
            self.last_center = (cx, cy)
            self.stationary_timer_start = current_time
            
        return False


class DetectionProcessor(threading.Thread):
    def __init__(self):
        # --- thread 화 수정 시작작---
        super().__init__(daemon=True)
        # --- 수정 끝 ---
        self.detector = HumanDetector()
        self.tracker = HumanTracker()
        self.alert_manager = AlertManager()
        self.reset_state()
        
        self.lock = threading.Lock()
        self.input_frame = None
        self.output_frame_for_stream = None
        self.output_bbox_for_ptz = None
        self.new_frame_event = threading.Event()
        self.running = True
        
    def reset_state(self):
        self.detection_mode = True
        self.was_tracking = False
        self.last_timestamp = "--:--:--"

    def run(self):
        """백그라운드 스레드에서 프레임 처리를 계속 수행합니다."""
        while self.running:
            self.new_frame_event.wait()
            if not self.running:
                break
                
            frame_to_process = None
            with self.lock:
                if self.input_frame is not None:
                    frame_to_process = self.input_frame
                    self.input_frame = None
            
            if frame_to_process is not None:
                from demo.utils.viz import draw_timestamp, process_masks, draw_detection_boxes
                
                disp = frame_to_process.copy()
                h, w = frame_to_process.shape[:2]
                
                cx, cy = w // 2, h // 2
                cv2.line(disp, (cx, 0), (cx, h), (0, 255, 0), 1)
                cv2.line(disp, (0, cy), (w, cy), (0, 255, 0), 1)
                cv2.circle(disp, (cx, cy), 4, (0, 0, 255), -1)

                now = time.time()
                draw_timestamp(disp, time.strftime("%H:%M:%S", time.localtime(now)))
                
                bbox_for_ptz = None

                if self.detection_mode:
                    persons = self.detector.detect(frame_to_process)
                    if persons:
                        bbox_for_ptz = persons[0]
                        self.tracker.initialize(frame_to_process, persons)
                        self.was_tracking = True
                        self.detection_mode = False
                        draw_detection_boxes(disp, persons)
                        self.alert_manager.send_alert(AlertCodes.PERSON_DETECTED, "PERSON_DETECTED")

                elif self.tracker.tracker is not None:
                    masks, has_mask = self.tracker.track(frame_to_process)
                    if has_mask:
                        bbox_for_ptz = process_masks(masks, disp, frame_to_process)
                        if self.tracker.check_stationary(bbox_for_ptz, now):
                            self.alert_manager.send_alert(AlertCodes.STATIONARY_BEHAVIOR, "STATIONARY BEHAVIOR DETECTED: analysis required")
                            threading.Thread(
                                target=self.post_stationary_bbox, 
                                args=(bbox_for_ptz, (w, h)), 
                                daemon=True
                            ).start()
                
                with self.lock:
                    self.output_frame_for_stream = disp
                    self.output_bbox_for_ptz = bbox_for_ptz

            self.new_frame_event.clear()

    def stop(self):
        """스레드를 안전하게 종료합니다."""
        self.running = False
        self.new_frame_event.set()

    def force_redetection(self):
        self.detection_mode = True
        self.was_tracking = False
        self.tracker.tracker = None
        return True
        
    def post_stationary_bbox(self, bbox: Tuple, frame_size: Tuple[int, int]):
        x1, y1, x2, y2 = bbox
        w, h = frame_size
        bbox_norm = [x1/w, y1/h, x2/w, y2/h]
        payload = {
            "signal_type": "stationary_behavior",
            "bbox_normalized": bbox_norm,
            "metadata": {"source": "detector.py"}
        }

        try:
            requests.post(DEMO_API, json=payload, timeout=1)
            print(f"[DAM] Sent stationary bbox {bbox_norm}")
        except Exception as e:
            print(f"[DAM] POST failed: {e}")
    
    def process_frame(self, frame: cv2.Mat) -> Tuple[cv2.Mat, Optional[Tuple]]:
        """
        메인 스레드에서는 이 메소드를 호출합니다.
        프레임을 버퍼에 넣고 즉시 최신 처리 결과를 반환합니다.
        """
        with self.lock:
            self.input_frame = frame
            # 처리된 최신 프레임과 bbox를 즉시 반환 (기다리지 않음)
            output_frame = self.output_frame_for_stream if self.output_frame_for_stream is not None else frame
            bbox = self.output_bbox_for_ptz
        
        self.new_frame_event.set() # 처리 스레드에게 새 프레임이 왔다고 알림
        
        return output_frame, bbox 