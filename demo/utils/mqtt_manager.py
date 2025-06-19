import time
from flask_socketio import SocketIO
from src.CADA.mqtt_utils import start_csi_mqtt_thread
from src.CADA.CADA_process import parse_and_normalize_payload

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