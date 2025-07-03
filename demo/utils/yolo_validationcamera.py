import autorootcwd
import cv2
import time
import threading
from ultralytics import YOLO
import os
import torch
import paho.mqtt.client as mqtt
from demo.config.settings import BROKER_ADDR, BROKER_PORT

class Yolo_ValidationCamera(threading.Thread):
    """YOLO 기반 사람 감지 검증용 카메라 클래스 (스레드)"""
    
    def __init__(self, rtsp_url=None, yolo_model_path=None):
        super().__init__(daemon=True)
        self.rtsp_url = rtsp_url or "rtsp://admin:kistWRLi^2rc@192.168.5.23:554/ISAPI/Streaming/channels/101"
        self.yolo_model_path = yolo_model_path or os.path.abspath("checkpoints/yolov10n.pt")
        self.model = YOLO(self.yolo_model_path)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[YOLO] Using device: {self.device}")
        
        self.mqtt_client = mqtt.Client()
        self.cap = None
        self.is_initialized = False
        
        self.x_start, self.y_start = 860, 0
        self.x_end, self.y_end = 1260, 1080

        self.running = False
        self.lock = threading.Lock()
        
    def initialize(self):
        """카메라 및 MQTT 초기화"""
        try:
            self.mqtt_client.connect(BROKER_ADDR, BROKER_PORT, 60)
            self.mqtt_client.loop_start()
            
            self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)

        
            self.is_initialized = True
            print(f"Validation camera initialized: {self.rtsp_url}")
            return True
        except Exception as e:
            print(f"[YOLO Init Error] {e}")
            return False

    def run(self):
        """백그라운드에서 사람 감지를 계속 수행"""
        self.running = True
        print("[YOLO] Background validation thread started")
        
        while self.running:
            if not self.is_initialized:
                time.sleep(1)
                continue
                
            try:
                person_detected = self.has_person()
                payload = "1" if person_detected else "0"
                with self.lock:
                    self.mqtt_client.publish("yolo/validation", payload)
            except Exception as e:
                print(f"[YOLO] Validation run error: {e}")
            
            # 실시간 스트림을 계속 소비하기 위해 sleep 제거
            # time.sleep(0.5)
    
    def has_person(self):
        """현재 프레임에서 사람이 있는지 확인"""
        if not self.is_initialized or self.cap is None:
            return False
            
        ret, frame = self.cap.read()
        if not ret or frame is None:
            # 스트림이 끊겼을 경우 재연결 시도
            print("[YOLO] Reconnecting to the stream...")
            self.cap.release()
            self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            time.sleep(1.0) # 재연결 안정화를 위한 대기 시간 추가
            return False
        
        cropped_frame = frame[self.y_start:self.y_end, self.x_start:self.x_end]
        
        results = self.model.predict(cropped_frame, device=self.device, classes=[0], verbose=False)
        return len(results[0].boxes) > 0

    def stop(self):
        """스레드 및 리소스 정리"""
        self.running = False
        time.sleep(0.6) # 스레드 루프가 멈출 시간을 줌
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            
        if self.cap:
            self.cap.release()
            
        print("[YOLO] Validation camera stopped.")
    
    def __del__(self):
        if self.running:
            self.stop()

def main():
    """독립 실행용 메인 함수"""
    validation_cam = Yolo_ValidationCamera()
    
    if not validation_cam.initialize():
        print("Failed to initialize validation camera")
        return
    
    validation_cam.start() # 스레드 시작
    
    print("YOLO validation camera running in background. Press 'q' to exit.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
        validation_cam.stop()
        validation_cam.join()
        print("Stopped.")

if __name__ == "__main__":
    main()