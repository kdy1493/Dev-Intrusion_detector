import cv2
import numpy as np

def draw_timestamp(frame, timestamp):
    h, w = frame.shape[:2]
    text_size, _ = cv2.getTextSize(timestamp, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
    text_w, text_h = text_size
    
    cv2.putText(
        frame,
        timestamp,
        (w - text_w - 10, text_h + 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2,
        cv2.LINE_AA
    )

def process_masks(m_np, disp, frame):
    h, w = disp.shape[:2]
    bbox_coords = None
    
    for i in range(m_np.shape[0]):
        mask = (m_np[i,0] > 0.5).astype(np.uint8)
        if mask.sum() == 0:
            continue
            
        mask = cv2.resize(mask, (w, h), cv2.INTER_NEAREST)

        overlay = disp.copy()
        overlay[mask>0] = (0, 255, 0)
        cv2.addWeighted(overlay, 0.5, disp, 0.7, 0, disp)
        
        ys, xs = np.where(mask>0)
        x1, y1, x2, y2 = xs.min(), ys.min(), xs.max(), ys.max()
        bbox_coords = (x1, y1, x2, y2)
        cv2.rectangle(disp, (x1,y1), (x2,y2), (0, 0, 255), 2)
        
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        cv2.circle(disp, (center_x, center_y), 4, (0, 0, 255), -1)

        cv2.circle(disp, (w//2, h//2), 4, (0, 0, 255), -1)
        
    disp = cv2.addWeighted(disp, 0.5, frame, 0.5, 0)
    return bbox_coords

def draw_detection_boxes(frame, persons):
    for box in persons:
        x1, y1 = box[0]
        x2, y2 = box[1]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2) 