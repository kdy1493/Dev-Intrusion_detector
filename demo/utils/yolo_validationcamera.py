import autorootcwd
import cv2
import time
from ultralytics import YOLO
import os
import torch
import paho.mqtt.client as mqtt
from demo.config.settings import BROKER_ADDR, BROKER_PORT

class Yolo_ValidationCamera:
    """YOLO 기반 사람 감지 검증용 카메라 클래스"""
    
    def __init__(self, rtsp_url=None, yolo_model_path=None):
        # RTSP URL 설정
        self.rtsp_url = rtsp_url or "rtsp://admin:kistWRLi^2rc@192.168.5.23:554/ISAPI/Streaming/channels/101"
        
        # YOLO 모델 로드
        self.yolo_model_path = yolo_model_path or os.path.abspath("checkpoints/yolov10n.pt")
        self.model = YOLO(self.yolo_model_path)
        
        # CUDA 디바이스 설정
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[YOLO] Using device: {self.device}")
        
        # MQTT 설정
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.connect(BROKER_ADDR, BROKER_PORT, 60)
        self.mqtt_client.loop_start()
        
        # 카메라 초기화
        self.cap = None
        self.is_initialized = False
        
        # 프레임 크롭 설정
        self.x_start, self.y_start = 860, 0
        self.x_end, self.y_end = 1260, 1080
        
    def initialize(self):
        """카메라 초기화"""
        self.cap = cv2.VideoCapture(self.rtsp_url)
        if not self.cap.isOpened():
            print(f"Error: Unable to open RTSP stream: {self.rtsp_url}")
            return False
        
        self.is_initialized = True
        print(f"Validation camera initialized: {self.rtsp_url}")
        return True
    
    def has_person(self):
        """현재 프레임에서 사람이 있는지 확인"""
        if not self.is_initialized:
            return False
            
        ret, frame = self.cap.read()
        if not ret:
            return False
        
        # 프레임 크롭
        cropped_frame = frame[self.y_start:self.y_end, self.x_start:self.x_end]
        
        # YOLO 사람 감지
        try:
            results = self.model.predict(cropped_frame, device=self.device, classes=[0], verbose=False)
            return len(results[0].boxes) > 0
        except Exception as e:
            print(f"YOLO prediction error: {e}")
            return False
    
    def get_person_detection_status(self):
        """사람 검출 상태 반환 및 MQTT 발행"""
        if self.has_person():
            # 사람 검출 시 MQTT로 "1" 발행
            self.mqtt_client.publish("yolo/validation", "1")
            return 1
        return None
    
    def get_frame(self):
        """원본 프레임 반환 (크롭된 상태)"""
        if not self.is_initialized:
            return None
            
        ret, frame = self.cap.read()
        if not ret:
            return None
        
        # 프레임 크롭
        cropped_frame = frame[self.y_start:self.y_end, self.x_start:self.x_end]
        return cropped_frame
    
    def release(self):
        """리소스 해제"""
        if self.cap:
            self.cap.release()
            self.is_initialized = False
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            
        cv2.destroyAllWindows()
    
    def __del__(self):
        self.release()


def main():
    """독립 실행용 메인 함수"""
    validation_cam = Yolo_ValidationCamera()
    
    if not validation_cam.initialize():
        print("Failed to initialize validation camera")
        return
    
    print("YOLO validation camera started. Press 'q' to exit.")
    
    while True:
        detection_status = validation_cam.get_person_detection_status()
        frame = validation_cam.get_frame()
        
        if frame is None:
            print("Error: Failed to receive frame. Exiting...")
            break
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] Person detection status: {detection_status}")
        
        cv2.imshow("YOLO Validation Camera", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    validation_cam.release()


if __name__ == "__main__":
    main()