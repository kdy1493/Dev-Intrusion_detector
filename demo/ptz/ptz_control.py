from __future__ import annotations
import time
from typing import Optional, Tuple
from demo.ptz.mqtt_publisher import MQTTPublisher


class PTZController:
    def __init__(
        self,
        publisher: MQTTPublisher,
        frame_wh: Tuple[int, int],
        init_angles: Tuple[int, int] = (120, 120),
        hfov: float = 58.0, vfov: float = 41.0,
        pan_dir: int = -1, tilt_dir: int = +1,
        deadzone_px: int = 6,
        max_step: float = 2.0,
        send_ivl_s: float = 0.12,
        smooth_alpha: float = 0.20,
        min_step_deg: float = 0.05,
        gain_scale: float = 0.6,
    ):
        self.pub = publisher
        self.w, self.h = frame_wh
        self.kx = (hfov / self.w) * pan_dir * gain_scale
        self.ky = (vfov / self.h) * tilt_dir * gain_scale

        self.dead = deadzone_px
        self.max_step = max_step
        self.alpha = smooth_alpha
        self.min_step = min_step_deg
        self.min_ivl = send_ivl_s

        self.pan, self.tilt = init_angles
        self.last_sent = 0.0

    @staticmethod
    def _clamp(v: float) -> int:
        return max(0, min(180, int(round(v))))

    def _within_deadzone(self, dx: float, dy: float) -> bool:
        return abs(dx) < self.dead and abs(dy) < self.dead

    def update(self, bbox: Optional[Tuple]) -> None:
        if bbox is None:
            return

        if len(bbox) == 2 and all(len(pt) == 2 for pt in bbox):
            (x1, y1), (x2, y2) = bbox
        elif len(bbox) == 4:
            x1, y1, x2, y2 = bbox
        else:
            return

        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        dx, dy = cx - self.w / 2, cy - self.h / 2
        if self._within_deadzone(dx, dy):
            return

        tgt_pan  = self._clamp(self.pan  + self.kx * dx)
        tgt_tilt = self._clamp(self.tilt + self.ky * dy)
        pan_next  = self.pan  + (tgt_pan  - self.pan)  * self.alpha
        tilt_next = self.tilt + (tgt_tilt - self.tilt) * self.alpha

        pan_step  = max(-self.max_step, min(self.max_step, pan_next  - self.pan))
        tilt_step = max(-self.max_step, min(self.max_step, tilt_next - self.tilt))
        if abs(pan_step) < self.min_step:
            pan_step = 0.0
        if abs(tilt_step) < self.min_step:
            tilt_step = 0.0

        pan_target  = self._clamp(self.pan  + pan_step)
        tilt_target = self._clamp(self.tilt + tilt_step)

        now = time.time()
        if now - self.last_sent < self.min_ivl:
            return

        for axis, target in (("pan", pan_target), ("tilt", tilt_target)):
            if axis == "pan" and target != self.pan:
                self.pan = target
                self.pub.publish("pan", self.pan)
                self.last_sent = now
            elif axis == "tilt" and target != self.tilt:
                self.tilt = target
                self.pub.publish("tilt", self.tilt)
                self.last_sent = now
