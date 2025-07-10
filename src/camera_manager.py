#!/usr/bin/env python3
"""CameraManager – OpenCV-FFmpeg wrapper for MJPEG / H.264 streams."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional

import cv2
import numpy as np


class CameraManager:
    def __init__(
        self,
        capture_dir: Path,
        width: int = 1280,
        height: int = 720,
        fps: int = 10,
    ) -> None:
        self.capture_dir = capture_dir
        self.capture_dir.mkdir(exist_ok=True)

        self.width, self.height = width, height
        self.fps = fps

        self.stream_url: str | None = None
        self.cap: cv2.VideoCapture | None = None  # live preview
        self.is_initialized: bool = False  # 카메라 초기화 상태

    # ────────────────────────── I/O ──────────────────────────
    def initialize_camera(self, stream_url: str) -> bool:
        self.stream_url = stream_url
        self.cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        ok = self.cap.isOpened()
        self.is_initialized = ok  # 초기화 상태 업데이트
        if ok:
            print(f"Camera ready: {self.width}×{self.height}@{self.fps}  ({stream_url})")
        else:
            print(f"Failed to open stream: {stream_url}")
        return ok

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        return (False, None) if self.cap is None else self.cap.read()

    # ─────────────────────── recording ───────────────────────
    def record_video(
        self,
        duration: int = 5,
        recording_fps: int = 5,
    ) -> Optional[Path]:
        if self.stream_url is None:
            print("Camera not initialized"); return None

        rec_cap = cv2.VideoCapture(self.stream_url, cv2.CAP_FFMPEG)
        rec_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not rec_cap.isOpened():
            print("Recording capture open failed"); return None

        out = self.capture_dir / f"video_{datetime.now():%Y%m%d_%H%M%S}.mp4"
        writer = cv2.VideoWriter(
            str(out),
            cv2.VideoWriter_fourcc(*"mp4v"),
            recording_fps,
            (self.width, self.height),
        )
        if not writer.isOpened():
            rec_cap.release(); print("VideoWriter init failed"); return None

        deadline = time.time() + duration
        frames = 0
        frame_interval = 1.0 / recording_fps  # 프레임 간격 계산
        next_frame_time = time.time()
        
        while time.time() < deadline:
            current_time = time.time()
            if current_time >= next_frame_time:
                ret, frame = rec_cap.read()
                if not ret:
                    break
                writer.write(cv2.resize(frame, (self.width, self.height)))
                frames += 1
                next_frame_time += frame_interval
            else:
                # FPS 제어를 위한 짧은 대기
                time.sleep(0.001)

        writer.release(); rec_cap.release()
        print(f"Saved {frames} frames → {out}")
        return out if frames else None

    # ─────────────────────── overlay ────────────────────────
    @staticmethod
    def add_status_overlay(
        frame: np.ndarray,
        recording: bool,
        queue_len: int,
    ) -> np.ndarray:
        txt = "RECORDING" if recording else "MONITORING"
        clr = (0, 0, 255) if recording else (0, 255, 0)
        cv2.putText(frame, txt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, clr, 2)
        cv2.putText(
            frame,
            f"Signals in queue: {queue_len}",
            (10, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )
        return frame

    # ─────────────────────── cleanup ────────────────────────
    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            self.is_initialized = False  # 초기화 상태 해제
        cv2.destroyAllWindows()

    def __del__(self) -> None:
        self.release()
