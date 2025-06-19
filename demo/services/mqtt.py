import threading
import time
import paho.mqtt.client as paho
from demo.config.settings import BROKER_ADDR, BROKER_PORT, STREAM_URL
from demo.services.mqtt_publisher import MQTTPublisher

class MQTTService: 
    def __init__(self, stream_manager):
        self.stream_manager = stream_manager
        self.client = None
        self.last_trigger_time = None
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
        print(f"[MQTT] Received message: '{payload}' (stream_active: {self.stream_manager.is_active()})")

        now = time.time()
        
        if payload == "1":
            if not self.stream_manager.is_active():
                print("[TRIGGER] 1 → stream ON")
                self.last_trigger_time = now
                threading.Thread(target=self._send_stream_on, daemon=True).start()
                self.stream_manager.start_stream()
            
            else:
                if self.last_trigger_time and (now - self.last_trigger_time) < 3:
                    return
                else:
                    print(f"[TRIGGER] stream OFF")
                    self.stream_manager.stop_stream()
                    self.last_trigger_time = None

        elif payload == "0" and self.stream_manager.is_active():
            print("[TRIGGER] 0 → stream OFF")
            self.stream_manager.stop_stream()
            self.last_trigger_time = None

        else:
            print(f"[MQTT] Ignored message: payload='{payload}', stream_active={self.stream_manager.is_active()}")
    
        
    def _send_stream_on(self):
        try:
            if not hasattr(self, "_fire_client"):
                self._fire_client = paho.Client()
                self._fire_client.connect(BROKER_ADDR, BROKER_PORT, 60)
            self._fire_client.publish("ptz/stream", "on", qos=0, retain=False)
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