import time, threading
from typing import Union
import paho.mqtt.client as mqtt
import sys
import os

from demo.config.settings import (
    BROKER_ADDR, BROKER_PORT, MQTT_PTZ_TOPIC,
    MQTT_PTZ_CLIENT_ID, MQTT_PTZ_KEEPALIVE
)

class MQTTPublisher:
    def __init__(
        self,
        broker_addr: str = BROKER_ADDR,
        broker_port: int = BROKER_PORT,
        topic: str = MQTT_PTZ_TOPIC,
        client_id: str = MQTT_PTZ_CLIENT_ID,
        keepalive: int = MQTT_PTZ_KEEPALIVE,
    ) -> None:
        self.broker_addr = broker_addr
        self.broker_port = broker_port
        self.topic = topic

        self.connected = False
        self._last_sent = {"pan": None, "tilt": None}
        self._pending   = {"pan": None, "tilt": None}

        self.client = mqtt.Client(client_id=client_id, clean_session=True)
        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.reconnect_delay_set(min_delay=0.2, max_delay=2)

        self.client.connect_async(self.broker_addr, self.broker_port, keepalive)
        self.client.loop_start()

        threading.Thread(target=self._watchdog, daemon=True).start()

    def _on_connect(self, *_):
        self.connected = True
        print(f"[MQTT] Connected → {self.broker_addr}:{self.broker_port}")

        for axis in ("pan", "tilt"):
            if self._pending[axis] is not None:
                self._raw_publish(axis, self._pending[axis])

    def _on_disconnect(self, *_):
        self.connected = False
        print("[MQTT] Disconnected – auto-reconnect")

    def _watchdog(self):
        while True:
            if not self.client.is_connected():
                try:
                    self.client.reconnect_async()
                except Exception:
                    pass
            time.sleep(5)

    @staticmethod
    def _clamp(angle: Union[int, float]) -> int:
        if not (0 <= angle <= 180):
            raise ValueError("angle must be 0–180")
        return int(angle)

    @staticmethod
    def _fmt(axis: str, ang: int) -> str:
        if axis not in ("pan", "tilt"):
            raise ValueError("axis must be pan|tilt")
        return f"{axis}, {ang}"

    def _raw_publish(self, axis: str, ang: int):
        payload = self._fmt(axis, ang)
        rc = self.client.publish(self.topic, payload, qos=1)[0]
        if rc == mqtt.MQTT_ERR_SUCCESS:
            self._last_sent[axis] = ang
            print(f"[PTZ] PTZ Command: {payload}")
        else:
            print(f"[MQTT] Publish failed (rc={rc})")

    def publish(self, axis: str, angle: Union[int, float]) -> None:
        ang = self._clamp(angle)
        self._pending[axis] = ang

        if not self.connected:
            return

        if self._last_sent.get(axis) == ang:
            return

        self._raw_publish(axis, ang)


if __name__ == "__main__":
    import uuid, os
    pub = MQTTPublisher(
        client_id=f"human_ptz_{os.getpid()}_{uuid.uuid4().hex[:4]}"
    )
    try:
        while True:
            pub.publish("pan", 120)
            time.sleep(0.3)
            pub.publish("tilt", 110)
            time.sleep(0.3)
    except KeyboardInterrupt:
        pub.client.loop_stop()
        pub.client.disconnect()
