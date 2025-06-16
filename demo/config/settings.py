import os
import torch
import cv2

# Path to YOLOv8 model checkpoint
YOLO_MODEL_PATH = os.path.abspath("checkpoints/yolov8n.pt")

# Path to SAM2 configuration file
SAM_CONFIG_PATH = "./configs/samurai/sam2.1_hiera_b+.yaml"

# Path to SAM2 model checkpoint
SAM_CHECKPOINT_PATH = os.path.abspath("checkpoints/sam2.1_hiera_base_plus.pt")

# Device selection for model inference
# Options: "cuda:0" for GPU, "cpu" for CPU
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"

# Web server settings
HOST = '0.0.0.0'
PORT = 5000
DEBUG = True

# Detection and tracking thresholds
STATIONARY_THRESHOLD = 5  # pixels
STATIONARY_TIME_THRESHOLD = 3.0  # seconds
MASK_THRESHOLD = 0.5  # confidence threshold for mask generation

# Camera settings
CAMERA_INDEX = 0
CAMERA_BACKEND = cv2.CAP_DSHOW