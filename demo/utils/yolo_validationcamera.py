import autorootcwd
import cv2
import time
from ultralytics import YOLO
import os

class Yolo_ValidationCamera:
    """YOLO 기반 사람 감지 검증용 카메라 클래스"""
    
    def __init__(self, rtsp_url=None, yolo_model_path=None):
        # RTSP URL 설정
        self.rtsp_url = rtsp_url or "rtsp://admin:kistWRLi^2rc@192.168.5.23:554/ISAPI/Streaming/channels/101"
        
        # YOLO 모델 로드
        self.yolo_model_path = yolo_model_path or os.path.abspath("checkpoints/yolov8n.pt")
        self.model = YOLO(self.yolo_model_path)
        
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
            results = self.model.predict(cropped_frame, classes=[0], verbose=False)  # class 0 = person
            return len(results[0].boxes) > 0
        except Exception as e:
            print(f"YOLO prediction error: {e}")
            return False
    
    def get_frame_with_detection(self):
        """감지 결과가 표시된 프레임 반환"""
        if not self.is_initialized:
            return None, False
            
        ret, frame = self.cap.read()
        if not ret:
            return None, False
        
        # 프레임 크롭
        cropped_frame = frame[self.y_start:self.y_end, self.x_start:self.x_end]
        
        # 사람 감지
        person_detected = self.has_person()
        
        # 감지 결과를 프레임에 표시
        self._draw_detection_results(cropped_frame, person_detected)
        
        # 타임스탬프 추가
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        height, width = cropped_frame.shape[:2]
        cv2.putText(cropped_frame, timestamp, (10, height-20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return cropped_frame, person_detected
    
    def _draw_detection_results(self, frame, has_person_detected):
        """감지 결과를 프레임에 표시"""
        if has_person_detected:
            # 사람 감지됨 - 녹색 테두리와 텍스트
            cv2.rectangle(frame, (10, 10), (300, 80), (0, 255, 0), 2)
            cv2.putText(frame, "PERSON DETECTED", (20, 40), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(frame, "CSI Trigger: VALID", (20, 65), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        else:
            # 사람 없음 - 빨간색 테두리와 텍스트
            cv2.rectangle(frame, (10, 10), (300, 80), (0, 0, 255), 2)
            cv2.putText(frame, "NO PERSON", (20, 40), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            cv2.putText(frame, "CSI Trigger: INVALID", (20, 65), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    
    def release(self):
        """리소스 해제"""
        if self.cap:
            self.cap.release()
            self.is_initialized = False
        cv2.destroyAllWindows()
    
    def __del__(self):
        self.release()


def main():
    """독립 실행용 메인 함수"""
    # ValidationCamera 인스턴스 생성
    validation_cam = Yolo_ValidationCamera()
    
    # 카메라 초기화
    if not validation_cam.initialize():
        print("Failed to initialize validation camera")
        return
    
    print("YOLO validation camera started. Press 'q' to exit.")
    
    # 메인 루프
    while True:
        frame, person_detected = validation_cam.get_frame_with_detection()
        
        if frame is None:
            print("Error: Failed to receive frame. Exiting...")
            break
        
        # 결과 출력
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] Person detected: {person_detected}")
        
        # 화면에 표시
        cv2.imshow("YOLO Validation Camera", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    validation_cam.release()


if __name__ == "__main__":
    main()