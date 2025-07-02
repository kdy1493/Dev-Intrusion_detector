import cv2
from ultralytics import YOLO
import torch

def main():
    rtsp_url = "rtsp://admin:kistWRLi^2rc@192.168.5.23:554/ISAPI/Streaming/channels/101"
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    model = YOLO("checkpoints/yolov10n.pt")
    device = "cuda" if torch.cuda.is_available() else "cpu"

    if not cap.isOpened():
        print(f"Error: Unable to open RTSP stream: {rtsp_url}")
        return

    print("RTSP 스트림을 표시합니다. 'q'를 누르면 종료합니다.")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("프레임을 읽을 수 없습니다.")
            break

        # 크롭 없이 전체 프레임 사용
        x_start, y_start = 860, 0
        x_end, y_end = 1280, 1080
        frame = frame[y_start:y_end, x_start:x_end]  # 필요시 크롭

        # YOLO 추론
        results = model.predict(frame, device=device, imgsz=640, classes=[0], verbose=True)
        print("감지된 사람 수:", len(results[0].boxes))

        # 원본 프레임만 표시
        cv2.imshow("RTSP Stream (YOLO 테스트)", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()