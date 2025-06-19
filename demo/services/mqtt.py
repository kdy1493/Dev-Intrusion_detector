import threading
import paho.mqtt.client as paho
from demo.config.settings import BROKER_ADDR, BROKER_PORT, STREAM_URL
from demo.services.mqtt_publisher import MQTTPublisher

class MQTTService: 
    def __init__(self, stream_manager):
        self.stream_manager = stream_manager
        self.client = None
        self._setup_mqtt_client()
        
    def _setup_mqtt_client(self):
        self.client = paho.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        
    def _on_connect(self, client, userdata, flags, rc):
        client.subscribe("ptz/trigger")
        print(f"[MQTT] Connected with result code {rc}")
        
    def _on_message(self, client, userdata, message):
        payload = message.payload.decode().strip()
        
        if payload == "1" and not self.stream_manager.is_active():
            print("[TRIGGER] 1 → stream ON")
            self._send_stream_on()
            self.stream_manager.start_stream()
            
        elif payload == "0" and self.stream_manager.is_active():
            print("[TRIGGER] 0 → stream OFF")
            self.stream_manager.stop_stream()
            
    def _send_stream_on(self):
        try:
            cli = paho.Client()
            cli.connect(BROKER_ADDR, BROKER_PORT, 60)
            cli.publish("ptz/stream", "on", qos=0, retain=False)
            cli.disconnect()
            print("[MQTT] ptz/stream → on (mjpg start)")
        except Exception as e:
            print("[MQTT] stream-on publish failed:", e)
            
    def start(self):
        try:
            self.client.connect(BROKER_ADDR, BROKER_PORT, 60)
            threading.Thread(target=self.client.loop_forever, daemon=True).start()
            print("[MQTT] Service started")
        except Exception as e:
            print(f"[MQTT] Failed to start service: {e}")
            
    def stop(self):
        if self.client:
            self.client.disconnect()
            print("[MQTT] Service stopped") 