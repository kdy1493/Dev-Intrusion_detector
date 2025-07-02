import autorootcwd
import cv2
import time
import os
import numpy as np
import threading
from flask import Flask, Response, render_template, jsonify, request
from flask_socketio import SocketIO
from demo.core.stream import StreamManager
from demo.core.detector import DetectionProcessor
from demo.services.cada import CADAService
from demo.services.mqtt import MQTTService
from demo.services.ptz import PTZService
from demo.utils.alerts import AlertManager, AlertCodes
from demo.config.settings import HOST, PORT, DEBUG

# ----- YOLO AND GATE ADDITION START -----
from demo.utils.yolo_validationcamera import Yolo_ValidationCamera
# ----- YOLO AND GATE ADDITION END -----

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
FFMPEG_OPTS = (
    "fflags nobuffer;"
    "flags low_delay;"
    "probesize 32;"
    "analyzeduration 0"
)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = FFMPEG_OPTS

class HumanDetectionApp:
    def __init__(self):
        self.app = Flask(__name__,
                        template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
        self.socketio = SocketIO(async_mode="threading")
        self.socketio.init_app(self.app)
        self.stream_manager = StreamManager()
        self.detection_processor = DetectionProcessor()
        self.cada_service = CADAService(self.socketio)
        self.mqtt_service = MQTTService(self.stream_manager)
        self.ptz_service = PTZService()
        self.ptz_initialized = False
        
        # ----- YOLO AND GATE ADDITION START -----
        # YOLO 검증 카메라 초기화
        self.yolo_validation_camera = None
        # ----- YOLO AND GATE ADDITION END -----
        
        threading.Thread(target=self._heavy_init, daemon=True).start()
        self._start_services()
        self._setup_routes()
        self._register_socketio_handlers()
        
    def _heavy_init(self):
        _ = DetectionProcessor()
        print("[INIT] models pre-loaded")
        
        # ----- YOLO AND GATE ADDITION START -----
        # YOLO 검증 카메라 시작
        try:
            self.yolo_validation_camera = Yolo_ValidationCamera()
            if self.yolo_validation_camera.initialize():
                print("[INIT] YOLO validation camera started")
                # YOLO 검증 카메라를 백그라운드에서 실행
                threading.Thread(target=self._run_yolo_validation, daemon=True).start()
            else:
                print("[INIT] Failed to start YOLO validation camera")
        except Exception as e:
            print(f"[INIT] YOLO validation camera error: {e}")
        # ----- YOLO AND GATE ADDITION END -----
        
    def _start_services(self):
        self.mqtt_service.start()
        self.cada_service.start()
        
    def _setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template('index.html')
        @self.app.route('/video_feed')
        def video_feed():
            return Response(
                self.get_stream_generator(),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )
        @self.app.route('/alerts')
        def alerts():
            def event_stream():
                self.detection_processor.alert_manager.send_alert(AlertCodes.SYSTEM_STARTED, "SYSTEM_STARTED: waiting for human")
                while True:
                    data = self.detection_processor.alert_manager.get_next_alert()
                    if data:
                        yield f"data: {data}\n\n"
                    else:
                        yield "data: \n\n"
            return Response(event_stream(), mimetype='text/event-stream')
        @self.app.route('/redetect', methods=['POST'])
        def redetect():
            success = self.force_redetection()
            if success:
                self.detection_processor.alert_manager.send_alert(AlertCodes.SYSTEM_STARTED, "SYSTEM_STARTED: waiting for human")
            return jsonify({'success': success})
        @self.app.route('/timestamp')
        def timestamp():
            return jsonify({'timestamp': self.get_last_timestamp()})
        @self.app.route('/analysis_result', methods=['POST'])
        def analysis_result():
            try:
                data = request.get_json()
                description = data.get('description', '')
                bbox_normalized = data.get('bbox_normalized', [])
                signal_type = data.get('signal_type', 'analysis')
                if description:
                    message = f"analysis result: {description}"
                    if bbox_normalized:
                        message += f" (BBox: {bbox_normalized})"
                    self.detection_processor.alert_manager.send_alert(
                        AlertCodes.INTRUSION_DETECTED,
                        message
                    )
                    return jsonify({
                        'status': 'success',
                        'message': 'Analysis result received and sent to web interface'
                    }), 200
                else:
                    return jsonify({
                        'status': 'error',
                        'message': 'No description provided'
                    }), 400
            except Exception as e:
                print(f"[WEB ERROR] : {e}")
                return jsonify({
                    'status': 'error',
                    'message': str(e)
                }), 500
                
    def _register_socketio_handlers(self):
        @self.socketio.on("connect", namespace="/csi")
        def on_connect():
            if self.cada_service.mqtt_manager:
                self.cada_service.mqtt_manager.start()
            print("[SocketIO] Client connected")
        @self.socketio.on("disconnect", namespace="/csi")
        def on_disconnect():
            print("[SocketIO] Client disconnected")
            
    def _initialize_ptz_if_needed(self, frame):
        if not self.ptz_initialized and frame is not None:
            h, w = frame.shape[:2]
            self.ptz_service.initialize(w, h)
            self.ptz_initialized = True
            
    def process_frame(self, frame):
        if frame is None:
            return None
        self._initialize_ptz_if_needed(frame)
        processed_frame, bbox_for_ptz = self.detection_processor.process_frame(frame)
        if self.ptz_initialized:
            self.ptz_service.update(bbox_for_ptz)
        return processed_frame
        
    def gen_frames(self):
        while True:
            if not self.stream_manager.is_active():
                blank = self.stream_manager.get_blank_frame()
                ok, buf = cv2.imencode('.jpg', blank)
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                       buf.tobytes() + b'\r\n')
                time.sleep(0.1)
                continue
            frame = self.stream_manager.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue
            processed_frame = self.process_frame(frame)
            if processed_frame is not None:
                ok, buf = cv2.imencode('.jpg', processed_frame,
                                       [int(cv2.IMWRITE_JPEG_QUALITY), 60])
                if ok:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                           buf.tobytes() + b'\r\n')
                           
    def get_stream_generator(self):
        return self.gen_frames()
        
    def get_last_timestamp(self):
        return self.detection_processor.last_timestamp
        
    def force_redetection(self):
        return self.detection_processor.force_redetection()
        
    def run(self):
        # ----- YOLO AND GATE ADDITION START -----
        try:
            self.app.run(host=HOST, port=PORT, debug=DEBUG)
        finally:
            # 서버 종료 시 YOLO 검증 카메라 정리
            if self.yolo_validation_camera:
                self.yolo_validation_camera.release()
        # ----- YOLO AND GATE ADDITION END -----

    # ----- YOLO AND GATE ADDITION START -----
    def _run_yolo_validation(self):
        """YOLO 검증 카메라를 백그라운드에서 지속적으로 실행"""
        print("[YOLO] Background validation started")
        while True:
            try:
                if self.yolo_validation_camera and self.yolo_validation_camera.is_initialized:
                    # 사람 검출 상태 확인 (MQTT 발행 포함)
                    detection_status = self.yolo_validation_camera.get_person_detection_status()
                    
                    # 검출 상태 로깅 (선택사항)
                    if detection_status == 1:
                        print("[YOLO] Person detected - MQTT published")
                    
                time.sleep(0.5)  # 0.5초 간격으로 검출
            except Exception as e:
                print(f"[YOLO] Validation error: {e}")
                time.sleep(1.0)  # 에러 시 1초 대기
    # ----- YOLO AND GATE ADDITION END -----

if __name__ == "__main__":
    app = HumanDetectionApp()
    app.run()