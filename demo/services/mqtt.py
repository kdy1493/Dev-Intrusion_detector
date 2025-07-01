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
        
        # ----- YOLO AND GATE ADDITION START -----
        # AND Gate 상태 관리
        self.csi_flag = False
        self.yolo_flag = False
        self.last_csi_time = 0
        self.last_yolo_time = 0
        self.csi_timeout = 5.0  # CSI 신호 타임아웃 (5초)
        self.yolo_timeout = 3.0  # YOLO 신호 타임아웃 (3초)
        # ----- YOLO AND GATE ADDITION END -----
        
        self._setup_mqtt_client()
        
    def _setup_mqtt_client(self):
        self.client = paho.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        # 연결 안정성 개선
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.enable_logger()
        
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            # ----- YOLO AND GATE ADDITION START -----
            client.subscribe("ptz/trigger")  # CSI 신호
            client.subscribe("yolo/validation")  # YOLO 검증 신호
            # ----- YOLO AND GATE ADDITION END -----
            print(f"[MQTT] Connected successfully to {BROKER_ADDR}:{BROKER_PORT}")
        else:
            print(f"[MQTT] Connection failed with result code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print(f"[MQTT] Unexpected disconnection (rc={rc})")
        # 자동 재연결이 설정되어 있으므로 별도 처리 불필요

#  기존 코드 주석 처리
    # def _on_message(self, client, userdata, message):
    #     payload = message.payload.decode().strip()
    #     print(f"[MQTT] Received message: '{payload}' (stream_active: {self.stream_manager.is_active()})")

    #     now = int(time.time())
        
    #     if payload == "1":
    #         print("debug")
    #         if not self.stream_manager.is_active():
    #             if now - self.last_trigger_time < 3:
    #                 self.last_trigger_time = now
    #                 return
    #             else:
    #                 # self.last_trigger_time = now
    #                 print("[TRIGGER] 1 → stream ON")
    #                 threading.Thread(target=self._send_stream_on, daemon=True).start()
    #                 self.stream_manager.start_stream()
    #                 self.last_trigger_time = now
            
    #         else:
    #             if now - self.last_trigger_time < 3:
    #                 self.last_trigger_time = now
    #                 return
    #             else:
    #                 print(f"[TRIGGER] stream OFF")
    #                 threading.Thread(target=self._send_stream_off, daemon=True).start()
    #                 self.stream_manager.stop_stream()
    #                 self.last_trigger_time = now

    #     elif payload == "0" and self.stream_manager.is_active():
    #         print("[TRIGGER] 0 → stream OFF")
    #         #threading.Thread(target=self._send_stream_off, daemon=True).start()
    #         self.stream_manager.stop_stream()
    #         self.last_trigger_time = now

    #     else:
    #         print(f"[MQTT] Ignored message: payload='{payload}', stream_active={self.stream_manager.is_active()}")
        
        
    def _on_message(self, client, userdata, message):
        # ----- YOLO AND GATE ADDITION START -----
        topic = message.topic
        payload = message.payload.decode().strip()
        now = int(time.time())
        
        print(f"[MQTT] Received '{payload}' on topic '{topic}' (stream_active: {self.stream_manager.is_active()})")
        
        # CSI 신호 처리
        if topic == "ptz/trigger":
            self._handle_csi_signal(payload, now)
        
        # YOLO 검증 신호 처리
        elif topic == "yolo/validation":
            self._handle_yolo_signal(payload, now)
        
        # AND Gate 평가
        self._evaluate_and_gate(now)
        # ----- YOLO AND GATE ADDITION END -----
    
    # ----- YOLO AND GATE ADDITION START -----
    def _handle_csi_signal(self, payload, now):
        """CSI 신호 처리"""
        if payload == "1":

            self.csi_flag = True
            self.last_csi_time = now
            print(f"[CSI] Activity detected at {now}")
        elif payload == "0":
            self.csi_flag = False
            self.last_csi_time = now
            print(f"[CSI] No activity at {now}")
    
    def _handle_yolo_signal(self, payload, now):
        """YOLO 검증 신호 처리"""
        if payload == "1":
            self.yolo_flag = True
            self.last_yolo_time = now
            print(f"[YOLO] Person detected at {now}")
        elif payload == "0":
            self.yolo_flag = False
            self.last_yolo_time = now
            print(f"[YOLO] No person at {now}")
    
    def _evaluate_and_gate(self, now):
        """AND Gate 평가 및 스트림 제어"""
        # 타임아웃 체크
        if now - self.last_csi_time > self.csi_timeout:
            self.csi_flag = False
        if now - self.last_yolo_time > self.yolo_timeout:
            self.yolo_flag = False
        
        # AND Gate 로직
        and_result = self.csi_flag and self.yolo_flag
        
        print(f"[AND] CSI: {self.csi_flag}, YOLO: {self.yolo_flag} → Result: {and_result}")
        
        # 스트림 제어
        if and_result and not self.stream_manager.is_active():
            # AND Gate True + 스트림 OFF → 스트림 ON
            if now - self.last_trigger_time >= 3:  # 디바운싱
                print("[AND] CSI + YOLO confirmed → stream ON")
                threading.Thread(target=self._send_stream_on, daemon=True).start()
                self.stream_manager.start_stream()
                self.last_trigger_time = now
        
        elif not and_result and self.stream_manager.is_active():
            # AND Gate False + 스트림 ON → 스트림 OFF
            if now - self.last_trigger_time >= 3:  # 디바운싱
                print("[AND] CSI or YOLO inactive → stream OFF")
                threading.Thread(target=self._send_stream_off, daemon=True).start()
                self.stream_manager.stop_stream()
                self.last_trigger_time = now
    # ----- YOLO AND GATE ADDITION END -----
        
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
            print(f"[MQTT] Connecting to {BROKER_ADDR}:{BROKER_PORT}...")
            self.client.connect(BROKER_ADDR, BROKER_PORT, keepalive=60)
            threading.Thread(target=self.client.loop_forever, daemon=True).start()
            # ----- YOLO AND GATE ADDITION START -----
            print("[MQTT] Service started with AND Gate")
            # ----- YOLO AND GATE ADDITION END -----
        except Exception as e:
            print(f"[MQTT] Failed to start service: {e}")
            # 재시도 로직 추가
            print("[MQTT] Will retry connection automatically...")
            
    def stop(self):
        if self.client:
            self.client.disconnect()
        print("[MQTT] Service stopped") 