import threading
import time
import paho.mqtt.client as paho
from demo.config.settings import BROKER_ADDR, BROKER_PORT, STREAM_URL
from demo.services.mqtt_publisher import MQTTPublisher

class MQTTService: 
    def __init__(self, stream_manager):
        self.publisher = MQTTPublisher()
        self.stream_manager = stream_manager
        self.client = None
        self.last_trigger_time = int(time.time())
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

        now = int(time.time())
        
        if payload == "1":
            print("debug")
            if not self.stream_manager.is_active():
                if now - self.last_trigger_time < 3:
                    self.last_trigger_time = now
                    return
                else:
                    # self.last_trigger_time = now
                    print("[TRIGGER] 1 → stream ON")
                    threading.Thread(target=self._send_stream_on, daemon=True).start()
                    self.stream_manager.start_stream()
                    self.last_trigger_time = now
            
            else:
                if now - self.last_trigger_time < 3:
                    self.last_trigger_time = now
                    return
                else:
                    print(f"[TRIGGER] stream OFF")
                    threading.Thread(target=self._send_stream_off, daemon=True).start()
                    self.stream_manager.stop_stream()
                    self.last_trigger_time = now

        elif payload == "0" and self.stream_manager.is_active():
            print("[TRIGGER] 0 → stream OFF")
            #threading.Thread(target=self._send_stream_off, daemon=True).start()
            self.stream_manager.stop_stream()
            self.last_trigger_time = now

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

    def _send_stream_off(self):
        try:
            if not hasattr(self, "_fire_client"):
                self._fire_client = paho.Client()
                self._fire_client.connect(BROKER_ADDR, BROKER_PORT, 60)
            self._fire_client.publish("ptz/stream", "off", qos=0, retain=False)
        except Exception as e:
            print("[MQTT] stream-off publish failed:", e)

            
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