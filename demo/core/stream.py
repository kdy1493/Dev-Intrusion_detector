import cv2
import threading
import time
import numpy as np
from typing import Optional
from demo.config.settings import STREAM_URL

class FrameGrabber(threading.Thread):
    def __init__(self, url: str | int):
        super().__init__(daemon=True)
        # URL이 정수인 경우 (카메라 인덱스) 그대로 사용, 문자열인 경우 FFMPEG 사용
        if isinstance(url, int):
            self.cap = cv2.VideoCapture(url)
        else:
            self.cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.frame = None
        self.lock = threading.Lock()
        self.running = True

    def run(self):
        while self.running and self.cap.isOpened():
            ret, frm = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frm
        self.cap.release()

    def read(self):
        with self.lock:
            if self.frame is None:
                return None
            return self.frame.copy()

    def stop(self):
        self.running = False

class StreamManager:
    def __init__(self, stream_url: str | int = STREAM_URL):
        self.stream_url = stream_url
        self.stream_active = False
        self.grabber: Optional[FrameGrabber] = None
        
    def start_stream(self):
        if not self.stream_active:
            self.grabber = FrameGrabber(self.stream_url)
            self.grabber.start()
            self.stream_active = True
            
    def stop_stream(self):
        if self.stream_active:
            self.stream_active = False
            if self.grabber:
                self.grabber.stop()
                self.grabber = None
                
    def get_frame(self) -> Optional[np.ndarray]:
        if not self.stream_active or self.grabber is None:
            return None
        return self.grabber.read()
    
    def is_active(self) -> bool:
        return self.stream_active
    
    def get_blank_frame(self) -> np.ndarray:
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(blank, "Waiting for trigger...", (50, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        return blank