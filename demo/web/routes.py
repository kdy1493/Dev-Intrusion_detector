from flask import Response, render_template, jsonify
from ..utils.alerts import AlertManager, AlertCodes

class RouteHandler:
    def __init__(self, app, alert_manager, app_instance):
        self.app = app
        self.alert_manager = alert_manager
        self.app_instance = app_instance
        self.setup_routes()
    
    def setup_routes(self):
        self.app.route('/')(self.index)
        self.app.route('/video_feed')(self.video_feed)
        self.app.route('/alerts')(self.alerts)
        self.app.route('/redetect', methods=['POST'])(self.redetect)
        self.app.route('/timestamp')(self.timestamp)
    
    def index(self):
        return render_template('index.html')
    
    def video_feed(self):
        return Response(
            self.app_instance.gen_frames(),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    
    def alerts(self):
        def event_stream():
            self.alert_manager.send_alert(AlertCodes.SYSTEM_STARTED, "SYSTEM_STARTED: waiting for human")
            while True:
                data = self.alert_manager.get_next_alert()
                if data:
                    yield f"data: {data}\n\n"
                else:
                    yield "data: \n\n"
        return Response(event_stream(), mimetype='text/event-stream')
    
    def redetect(self):
        success = self.app_instance.force_redetection()
        if success:
            self.alert_manager.send_alert(AlertCodes.SYSTEM_STARTED, "SYSTEM_STARTED: waiting for human")
        return jsonify({'success': success})
    
    def timestamp(self):
        return jsonify({'timestamp': self.app_instance.last_timestamp}) 