from demo.services.mqtt_publisher import MQTTPublisher
from demo.services.ptz_controller import PTZController
from demo.config.settings import (
    BROKER_ADDR, BROKER_PORT, MQTT_PTZ_TOPIC, MQTT_PTZ_CLIENT_ID,
    PTZ_INIT_PAN, PTZ_INIT_TILT, PTZ_PAN_DIR, PTZ_TILT_DIR,
    PTZ_DEADZONE_PX, PTZ_MIN_STEP_DEG, PTZ_SMOOTH_ALPHA
)

class PTZService:
    def __init__(self):
        self.publisher = None
        self.controller = None
        self._initialized = False
        
    def initialize(self, frame_width: int, frame_height: int):
        if self._initialized:
            return

        self.publisher = MQTTPublisher(
            broker_addr=BROKER_ADDR,
            broker_port=BROKER_PORT,
            topic=MQTT_PTZ_TOPIC,
            client_id=MQTT_PTZ_CLIENT_ID,
        )
        
        self.controller = PTZController(
            publisher=self.publisher,
            frame_wh=(frame_width, frame_height),
            init_angles=(PTZ_INIT_PAN, PTZ_INIT_TILT),
            pan_dir=PTZ_PAN_DIR,
            tilt_dir=PTZ_TILT_DIR,
            deadzone_px=PTZ_DEADZONE_PX,
            min_step_deg=PTZ_MIN_STEP_DEG,
            smooth_alpha=PTZ_SMOOTH_ALPHA,
        )
        
        self._initialized = True
        print("[PTZ] Service initialized")
        
    def update(self, bbox):
        if self.controller:
            self.controller.update(bbox)
            
    def get_controller(self):
        return self.controller
        
    def get_publisher(self):
        return self.publisher 