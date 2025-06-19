import time
from flask_socketio import SocketIO
from src.CADA.mqtt_utils import start_csi_mqtt_thread
from src.CADA.CADA_process import parse_and_normalize_payload
import paho.mqtt.client as paho

class MQTTManager:
    def __init__(self, socketio: SocketIO, topics: list, broker_address: str, broker_port: int,
                 subcarriers: int, indices_to_remove: list, buffer_manager, sliding_processors: dict,
                 fps_limit: int = 10):
        self.socketio = socketio
        self.topics = topics
        self.broker_address = broker_address
        self.broker_port = broker_port
        self.subcarriers = subcarriers
        self.indices_to_remove = indices_to_remove
        self.buffer_manager = buffer_manager
        self.sliding_processors = sliding_processors
        self.fps_limit = fps_limit
        self._mqtt_started = False
        self.time_last_emit = {}
        self.trigger_cli = paho.Client()
        self.trigger_cli.on_message = self._on_trigger_message
        self.trigger_cli.connect(broker_address, broker_port, 60)
        self.trigger_cli.subscribe("ptz/trigger")
        self.trigger_cli.loop_start()

        # --- NEW: 트리거 상태 관리 ------------------------
        self._last_trigger_state = 0   # 0=OFF, 1=ON
        self._last_activity_time = 0.0 # 최근 flag>0 시각
        self._off_delay_sec = 2.0      # inactivity 후 OFF 전송 지연

    def start(self):
        if self._mqtt_started:
            return
        start_csi_mqtt_thread(
            message_handler=self.mqtt_handler,
            topics=self.topics,
            broker_address=self.broker_address,
            broker_port=self.broker_port,
            daemon=True,
        )
        self._mqtt_started = True

    def mqtt_handler(self, topic: str, payload: str):
        now = time.time()
        prev_emit = self.time_last_emit.get(topic, 0.0)

        parsed = parse_and_normalize_payload(
            payload, topic, self.subcarriers, self.indices_to_remove,
            self.buffer_manager.mu_bg_dict, self.buffer_manager.sigma_bg_dict)
        if parsed is None:
            return
        amp_z, pkt_time = parsed
        self.buffer_manager.timestamp_buffer[topic].append(pkt_time)
        self.sliding_processors[topic].push(amp_z, pkt_time)

        if not self.buffer_manager.cada_feature_buffers["activity_detection"][topic]:
            return

        idx = -1
        activity = self.buffer_manager.cada_feature_buffers["activity_detection"][topic][idx]
        flag = self.buffer_manager.cada_feature_buffers["activity_flag"][topic][idx]
        threshold = self.buffer_manager.cada_feature_buffers["threshold"][topic][idx]
        ts_ms = int(pkt_time.timestamp()*1000)

        if (now - prev_emit) < 1.0/self.fps_limit:
            return
        self.time_last_emit[topic] = now

        self.socketio.emit("cada_result", {
            "topic": topic,
            "timestamp_ms": ts_ms,
            "activity": float(activity),
            "flag": int(flag),
            "threshold": float(threshold),
        }, namespace="/csi")

        # -------- Trigger publish with hysteresis ----------
        if flag > 0:
            # 활동 감지: 스트림 ON (변경 시에만 전송)
            if self._last_trigger_state == 0:
                self.trigger_cli.publish("ptz/trigger", "1")
                self._last_trigger_state = 1
        # OFF 신호는 DetectionProcessor 에서 인물 소실 시점에 발행 

    def _on_trigger_message(self, client, userdata, msg):
        """브로커로부터 ptz/trigger 메시지를 수신해 내부 상태를 동기화"""
        payload = msg.payload.decode().strip()
        if payload == "1":
            self._last_trigger_state = 1
        elif payload == "0":
            self._last_trigger_state = 0 