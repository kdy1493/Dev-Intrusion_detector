import time
import paho.mqtt.client as mqtt

class MQTTPublisher:
    def __init__(
        self,
        broker_addr: str,
        broker_port: int,
        topic: str,
        client_id: str = None
    ):
        self.topic = topic
        self.client = mqtt.Client(
            client_id=client_id or "ptz_pub",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        def on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                print("[MQTT] Publisher connected")
            else:
                print(f"[MQTT] Publisher connect failed, rc={rc}")
        self.client.on_connect = on_connect

        self.client.connect(broker_addr, broker_port, keepalive=60)
        self.client.loop_start()

        self._last_cmd = None

    def publish(self, cmd: str):
        if cmd == self._last_cmd:
            return
        result = self.client.publish(self.topic, payload=cmd, qos=0)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"[MQTT] Published PTZ command: {cmd}")
            self._last_cmd = cmd
        else:
            print(f"[MQTT] Publish failed, rc={result.rc}")

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()