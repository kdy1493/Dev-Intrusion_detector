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

# Camera streaming settingsAdd commentMore actions
STREAM_URL = 1  # 1번 인덱스 카메라 사용
BROKER_ADDR = "61.252.57.136"
BROKER_PORT = 4991

# PTZ MQTT settings
MQTT_PTZ_TOPIC = "ptz/control"
MQTT_PTZ_CLIENT_ID = "human_app_ptz"
MQTT_PTZ_KEEPALIVE = 15

# PTZ control settings
PTZ_INIT_PAN = 120
PTZ_INIT_TILT = 120
PTZ_PAN_DIR = -1
PTZ_TILT_DIR = 1
PTZ_DEADZONE_PX = 5
PTZ_MIN_STEP_DEG = 0.05
PTZ_SMOOTH_ALPHA = 0.40

# DAM API settings
DEMO_API = "http://localhost:5100/trigger_recording"

CSI_TOPIC = ["L0382/ESP/8"]
# CSI MQTT settings
CSI_TOPICS = [
    "L0382/ESP/1",
    "L0382/ESP/2",
    "L0382/ESP/3",
    "L0382/ESP/4",
    "L0382/ESP/5",
    "L0382/ESP/6",
    "L0382/ESP/7",
    "L0382/ESP/8",
]
CSI_INDICES_TO_REMOVE = list(range(21, 32))
CSI_SUBCARRIERS = 52
CSI_WINDOW_SIZE = 320
CSI_STRIDE = 40
CSI_SMALL_WIN_SIZE = 64
CSI_FPS_LIMIT = 10