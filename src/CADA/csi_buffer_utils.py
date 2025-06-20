"""
csi_buffer_utils.py
----
Utility module for real-time CSI data processing and buffer management.

Key Functions
----
• RealtimeBufferManager class: Real-time CSI feature buffer management.
• process_realtime_csi function: Real-time MQTT CSI payload processing.
• extract_cada_features function: CADA feature extraction.
• load_calibration_data function: Load calibration CSV.
• parse_custom_timestamp function: ESP custom timestamp conversion.
"""

import autorootcwd
import numpy as np
from collections import deque


class RealtimeCSIBufferManager:
    """Class to manage all buffers for real-time CSI processing"""
    
    def __init__(self, topics, buffer_size=512, window_size=64):
        """
        Parameters:
            topics : List of MQTT topics
            buffer_size : Maximum buffer size
            window_size : Window size
        """
        self.topics = topics
        self.buffer_size = buffer_size
        self.window_size = window_size
        
        # Basic buffers
        self.timestamp_buffer = {topic: deque(maxlen=buffer_size) for topic in topics}
        
        # Buffers for CADA activity detection
        self.cada_csi_buffers = {topic: deque(maxlen=buffer_size) for topic in topics}
        self.cada_feature_buffers = {
            'activity_detection': {topic: deque(maxlen=buffer_size) for topic in topics},
            'activity_flag': {topic: deque(maxlen=buffer_size) for topic in topics},
            'threshold': {topic: deque(maxlen=buffer_size) for topic in topics}
        }
        
        # CADA state variables
        self.cada_mean_buffers = {topic: deque(maxlen=100) for topic in topics}
        self.cada_prev_samples = {topic: np.zeros(window_size) for topic in topics}
        self.cada_ewma_states = {topic: 0.0 for topic in topics}
        
        # Calibration data
        self.mu_bg_dict = {}
        self.sigma_bg_dict = {}
    
    def get_combined_features(self):
        """Return dictionary of CADA activity detection features"""
        combined = {}
        
        # Add CADA features
        for feat_name, feat_buffer in self.cada_feature_buffers.items():
            combined[feat_name] = feat_buffer
        
        return combined
    
    def clear_all_buffers(self):
        """Clear all buffers"""
        for topic in self.topics:
            self.timestamp_buffer[topic].clear()
            self.cada_csi_buffers[topic].clear()
            
            for feat_buffer in self.cada_feature_buffers.values():
                feat_buffer[topic].clear()
            
            self.cada_mean_buffers[topic].clear()
            self.cada_prev_samples[topic] = np.zeros(self.window_size)
            self.cada_ewma_states[topic] = 0.0



