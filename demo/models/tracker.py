import cv2
import numpy as np
from sam2.build_sam import build_sam2_object_tracker
from ..config.settings import SAM_CONFIG_PATH, SAM_CHECKPOINT_PATH, DEVICE, MASK_THRESHOLD

class HumanTracker:
    def __init__(self):
        self.tracker = None
        self.last_center = None
        self.stationary_timer_start = None
    
    def initialize(self, frame, persons):
        self.tracker = build_sam2_object_tracker(
            num_objects=len(persons),
            config_file=SAM_CONFIG_PATH,
            ckpt_path=SAM_CHECKPOINT_PATH,
            device=DEVICE,
            verbose=False
        )
        self.tracker.track_new_object(
            img=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
            box=np.array(persons)
        )
    
    def track(self, frame):
        if self.tracker is None:
            return None, False
            
        out = self.tracker.track_all_objects(img=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        masks = out.get("pred_masks")
        has_mask = False
        
        if masks is not None:
            m_np = masks.cpu().numpy()
            for i in range(m_np.shape[0]):
                if (m_np[i,0] > MASK_THRESHOLD).sum() > 0:
                    has_mask = True
                    break
                    
        return m_np if has_mask else None, has_mask
    
    def check_stationary(self, bbox_coords, current_time):
        if bbox_coords is None:
            return False
            
        x1, y1, x2, y2 = bbox_coords
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        
        if self.last_center is None:
            self.last_center = (cx, cy)
            self.stationary_timer_start = current_time
            return False
            
        dist = np.hypot(cx - self.last_center[0], cy - self.last_center[1])
        
        if dist < 5:
            if self.stationary_timer_start and current_time - self.stationary_timer_start >= 3.0:
                self.stationary_timer_start = None
                return True
        else:
            self.last_center = (cx, cy)
            self.stationary_timer_start = current_time
            
        return False 