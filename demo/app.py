import autorootcwd
import os
import time
import cv2
import torch
from flask import Flask, render_template, Response, request, jsonify
from flask_socketio import SocketIO
from demo.models.detector import HumanDetector
from demo.models.tracker import HumanTracker
from demo.utils.visualization import draw_timestamp, process_masks, draw_detection_boxes
from demo.web.routes import RouteHandler
from demo.utils.alerts import AlertManager, AlertCodes
from demo.config.settings import (
    HOST, PORT, DEBUG, CAMERA_INDEX, CAMERA_BACKEND
)
from src.CADA.realtime_csi_handler_utils import create_buffer_manager, load_calibration_data
from src.CADA.CADA_process import SlidingCadaProcessor
from demo.utils.mqtt_manager import MQTTManager
from demo.config.mqtt_settings import (
    TOPICS, INDICES_TO_REMOVE, SUBCARRIERS, CADA_WINDOW_SIZE,
    CADA_STRIDE, SMALL_WIN_SIZE, FPS_LIMIT, BROKER_ADDR, BROKER_PORT
)

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

socketio = SocketIO(async_mode="threading")  

buf_mgr = None  # type: ignore
sliding_processors = {}
mqtt_manager = None

last_timestamp = "--:--:--"

class HumanDetectionApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.alert_manager = AlertManager()
        self.detector = HumanDetector()
        self.tracker = HumanTracker()
        self.route_handler = RouteHandler(self.app, self.alert_manager, self)
        self.reset_state()

        socketio.init_app(self.app, async_mode="threading")
        self._initialize_cada()
    
    def _initialize_cada(self):
        global buf_mgr, sliding_processors, mqtt_manager
        buf_mgr = create_buffer_manager(TOPICS)
        load_calibration_data(TOPICS, buf_mgr.mu_bg_dict, buf_mgr.sigma_bg_dict)
        for t in TOPICS:
            buf_mgr.cada_ewma_states[t] = 0.0

        sliding_processors = {
            t: SlidingCadaProcessor(
                topic=t,
                buffer_manager=buf_mgr,
                mu_bg_dict=buf_mgr.mu_bg_dict,
                sigma_bg_dict=buf_mgr.sigma_bg_dict,
                window_size=CADA_WINDOW_SIZE,
                stride=CADA_STRIDE,
                small_win_size=SMALL_WIN_SIZE,
                threshold_factor=2.5,
            ) for t in TOPICS
        }

        mqtt_manager = MQTTManager(
            socketio=socketio,
            topics=TOPICS,
            broker_address=BROKER_ADDR,
            broker_port=BROKER_PORT,
            subcarriers=SUBCARRIERS,
            indices_to_remove=INDICES_TO_REMOVE,
            buffer_manager=buf_mgr,
            sliding_processors=sliding_processors,
            fps_limit=FPS_LIMIT
        )
    
    def reset_state(self):
        self.detection_mode = True
        self.was_tracking = False
        self.last_timestamp = "--:--:--"
    
    def force_redetection(self):
        self.detection_mode = True
        self.was_tracking = False
        self.tracker.tracker = None
        return True
    
    def process_frame(self, frame):
        disp = frame.copy()
        now = time.time()
        ts_str = time.strftime("%H:%M:%S", time.localtime(now))
        self.last_timestamp = ts_str
        draw_timestamp(disp, ts_str)
        
        if self.detection_mode:
            persons = self.detector.detect(frame)
            if persons:
                self.tracker.initialize(frame, persons)
                self.was_tracking = True
                self.detection_mode = False
                self.alert_manager.send_alert(AlertCodes.PERSON_DETECTED, "PERSON_DETECTED")
                draw_detection_boxes(disp, persons)
        elif self.tracker.tracker is not None:
            masks, has_mask = self.tracker.track(frame)
            if has_mask:
                bbox_coords = process_masks(masks, disp, frame)
                if self.tracker.check_stationary(bbox_coords, now):
                    self.alert_manager.send_alert(AlertCodes.STATIONARY_BEHAVIOR, 
                                                "STATIONARY BEHAVIOR DETECTED: analysis required")
            elif self.was_tracking:
                self.alert_manager.send_alert(AlertCodes.PERSON_LOST, "PERSON_LOST")
                self.reset_state()
        
        return disp
    
    def gen_frames(self):
        cap = cv2.VideoCapture(CAMERA_INDEX, CAMERA_BACKEND)
        if not cap.isOpened():
            raise RuntimeError("camera is not opened")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            disp = self.process_frame(frame)
            
            ret2, buf = cv2.imencode('.jpg', disp)
            if not ret2:
                continue
                
            frame_bytes = buf.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' +
                   frame_bytes +
                   b'\r\n')
            time.sleep(0.01)
        
        cap.release()
    
    def run(self):
        self.app.run(host=HOST, port=PORT, debug=DEBUG)

@socketio.on("connect", namespace="/csi")
def on_connect():
    if mqtt_manager:
        mqtt_manager.start()
    print("[SocketIO] Client connected")

@socketio.on("disconnect", namespace="/csi")
def on_disconnect():
    print("[SocketIO] Client disconnected")

if __name__ == '__main__':
    app = HumanDetectionApp()
    HumanDetectionApp().run()