from ultralytics import YOLO
from ..config.settings import YOLO_MODEL_PATH, DEVICE

class HumanDetector:
    def __init__(self):
        self.model = YOLO(YOLO_MODEL_PATH)
    
    def detect(self, frame):
        persons = []
        results = self.model.predict(frame, classes=[0], device=DEVICE, verbose=False)

        max_conf = 0
        best_box = None
        
        for res in results:
            for box in res.boxes:
                conf = float(box.conf[0])
                if conf > max_conf:
                    max_conf = conf
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    best_box = [[x1, y1], [x2, y2]]
        
        if best_box is not None:
            persons.append(best_box)
        
        return persons 