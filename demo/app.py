import autorootcwd, os, time, cv2, torch, threading, requests, threading
from flask import Flask, render_template, Response, request, jsonify
from flask_socketio import SocketIO
from demo.models.detector import HumanDetector
from demo.models.tracker import HumanTracker
from demo.utils.visualization import draw_timestamp, process_masks, draw_detection_boxes
from demo.web.routes import RouteHandler
from demo.utils.alerts import AlertManager, AlertCodes
from demo.config.settings import (
    HOST, PORT, DEBUG, CAMERA_INDEX, CAMERA_BACKEND,
    BROKER_ADDR, BROKER_PORT, MQTT_PTZ_TOPIC, MQTT_PTZ_CLIENT_ID,
    CSI_TOPICS, CSI_INDICES_TO_REMOVE, CSI_SUBCARRIERS,
    CSI_WINDOW_SIZE, CSI_STRIDE, CSI_SMALL_WIN_SIZE,
    CSI_FPS_LIMIT, STREAM_URL, CSI_TOPIC
)
from src.CADA.realtime_csi_handler_utils import create_buffer_manager, load_calibration_data
from src.CADA.CADA_process import SlidingCadaProcessor
from demo.utils.mqtt_manager import MQTTManager
from demo.ptz.mqtt_publisher import MQTTPublisher
from demo.ptz.ptz_control import PTZController

DEMO_API = "http://localhost:5100/trigger_recording"

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

socketio = SocketIO(async_mode="threading")  

buf_mgr = None
sliding_processors = {}
mqtt_manager = None

last_timestamp = "--:--:--"

mqtt_pub = MQTTPublisher(
    broker_addr=BROKER_ADDR,
    broker_port=BROKER_PORT,
    topic=MQTT_PTZ_TOPIC,
    client_id=MQTT_PTZ_CLIENT_ID,
)

FFMPEG_OPTS = (
    "fflags nobuffer;"
    "flags low_delay;"
    "probesize 32;"
    "analyzeduration 0"
)

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = FFMPEG_OPTS

STREAM_URL = STREAM_URL

socketio = SocketIO(async_mode="threading")

def post_stationary_bbox(bbox, frame_size):
    x1, y1, x2, y2 = bbox
    w, h = frame_size
    bbox_norm = [x1/w, y1/h, x2/w, y2/h]
    payload = {
        "signal_type": "stationary_behavior",
        "bbox_normalized": bbox_norm,
        "metadata": {"source": "app.py"}
    }

    try:
        requests.post(DEMO_API, json=payload, timeout=1)
        print(f"[DAM] Sent stationary bbox {bbox_norm}")
    except Exception as e:
        print(f"[DAM] POST failed: {e}")

class FrameGrabber(threading.Thread):
    def __init__(self, url: str):
        super().__init__(daemon=True)
        self.cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.frame = None
        self.lock = threading.Lock()
        self.running = True

    def run(self):
        while self.running and self.cap.isOpened():
            ret, frm = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frm
        self.cap.release()

    def read(self):
        with self.lock:
            if self.frame is None:
                return None
            return self.frame.copy()

    def stop(self):
        self.running = False


class HumanDetectionApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.alert_manager = AlertManager()
        self.detector = HumanDetector()
        self.tracker = HumanTracker()
        self.route_handler = RouteHandler(self.app, self.alert_manager, self)
        self.reset_state()
        self.ptz = None

        socketio.init_app(self.app, async_mode="threading")
        self._initialize_cada()

        self.grabber = FrameGrabber(STREAM_URL)
        self.grabber.start()
    
    def _initialize_cada(self):
        global buf_mgr, sliding_processors, mqtt_manager
        buf_mgr = create_buffer_manager(CSI_TOPIC)
        load_calibration_data(CSI_TOPIC, buf_mgr.mu_bg_dict, buf_mgr.sigma_bg_dict)
        for t in CSI_TOPIC:
            buf_mgr.cada_ewma_states[t] = 0.0

        sliding_processors = {
            t: SlidingCadaProcessor(
                topic=t,
                buffer_manager=buf_mgr,
                mu_bg_dict=buf_mgr.mu_bg_dict,
                sigma_bg_dict=buf_mgr.sigma_bg_dict,
                window_size=CSI_WINDOW_SIZE,
                stride=CSI_STRIDE,
                small_win_size=CSI_SMALL_WIN_SIZE,
                threshold_factor=2.5,
            ) for t in CSI_TOPIC
        }

        mqtt_manager = MQTTManager(
            socketio=socketio,
            topics=CSI_TOPIC,
            broker_address=BROKER_ADDR,
            broker_port=BROKER_PORT,
            subcarriers=CSI_SUBCARRIERS,
            indices_to_remove=CSI_INDICES_TO_REMOVE,
            buffer_manager=buf_mgr,
            sliding_processors=sliding_processors,
            fps_limit=CSI_FPS_LIMIT
        )


    def reset_state(self):
        self.detection_mode = True
        self.was_tracking = False
        self.last_timestamp = "--:--:--"
    
    def force_redetection(self):
        self.detection_mode = True
        self.was_tracking = False
        self.tracker.tracker = None
        return True
    
    def process_frame(self, frame):
        disp = frame.copy()
        now = time.time()
        ts_str = time.strftime("%H:%M:%S", time.localtime(now))
        self.last_timestamp = ts_str
        draw_timestamp(disp, ts_str)
        
        if self.detection_mode:
            persons = self.detector.detect(frame)
            if persons:
                self.tracker.initialize(frame, persons)
                self.was_tracking = True
                self.detection_mode = False
                self.alert_manager.send_alert(AlertCodes.PERSON_DETECTED, "PERSON_DETECTED")
                draw_detection_boxes(disp, persons)
        elif self.tracker.tracker is not None:
            masks, has_mask = self.tracker.track(frame)
            if has_mask:
                bbox_coords = process_masks(masks, disp, frame)
                if self.tracker.check_stationary(bbox_coords, now):
                    self.alert_manager.send_alert(AlertCodes.STATIONARY_BEHAVIOR, 
                                                "STATIONARY BEHAVIOR DETECTED: analysis required")
            elif self.was_tracking:
                self.alert_manager.send_alert(AlertCodes.PERSON_LOST, "PERSON_LOST")
                self.reset_state()
        
        return disp

    def process_frame(self, frame):
        disp = frame.copy()
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        cv2.line(disp, (cx, 0), (cx, h), (0, 255, 0), 1)
        cv2.line(disp, (0, cy), (w, cy), (0, 255, 0), 1)
        cv2.circle(disp, (cx, cy), 4, (0, 0, 255), -1)

        now = time.time()
        draw_timestamp(disp, time.strftime("%H:%M:%S", time.localtime(now)))
        bbox_for_ptz = None

        if self.detection_mode:
            persons = self.detector.detect(frame)
            if persons:
                bbox_for_ptz = persons[0]
                self.tracker.initialize(frame, persons)
                self.was_tracking = True
                self.detection_mode = False
                draw_detection_boxes(disp, persons)
                self.alert_manager.send_alert(AlertCodes.PERSON_DETECTED, "PERSON_DETECTED")

        elif self.tracker.tracker is not None:
            masks, has_mask = self.tracker.track(frame)
            if has_mask:
                bbox_for_ptz = process_masks(masks, disp, frame)
                if self.tracker.check_stationary(bbox_for_ptz, now):
                    self.alert_manager.send_alert(AlertCodes.STATIONARY_BEHAVIOR,
                                                  "STATIONARY BEHAVIOR DETECTED: analysis required")
                    threading.Thread(target=post_stationary_bbox, args=(bbox_for_ptz, (w, h)), daemon=True).start()
            elif self.was_tracking:
                self.alert_manager.send_alert(AlertCodes.PERSON_LOST, "PERSON_LOST")
                self.reset_state()

        if self.ptz is None:
            self.ptz = PTZController(
                publisher=mqtt_pub,
                frame_wh=(w, h),
                init_angles=(120, 120),
                pan_dir=-1, tilt_dir=+1,
                deadzone_px = 5,
                min_step_deg = 0.05,
                smooth_alpha = 0.40,
            )

        self.ptz.update(bbox_for_ptz)
        return disp

    def gen_frames(self):
        while True:
            frame = self.grabber.read()
            if frame is None:
                time.sleep(0.01)
                continue

            disp = self.process_frame(frame)
            ok, buf = cv2.imencode('.jpg', disp,
                                   [int(cv2.IMWRITE_JPEG_QUALITY), 60])
            if not ok:
                continue

            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                   buf.tobytes() + b'\r\n')

    def run(self):
        self.app.run(host=HOST, port=PORT, debug=DEBUG)

@socketio.on("connect", namespace="/csi")
def on_connect():
    if mqtt_manager:
        mqtt_manager.start()
    print("[SocketIO] Client connected")

@socketio.on("disconnect", namespace="/csi")
def on_disconnect():
    print("[SocketIO] Client disconnected")

if __name__ == "__main__":
    HumanDetectionApp().run()