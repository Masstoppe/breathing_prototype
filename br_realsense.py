

import pyrealsense2 as rs
import numpy as np
import collections


#CONFIGURATION
MAX_DISPLACEMENT_MM = 6.0 # max inhale movement in millimeter 
SMOOTHING_WINDOW = 10  # number of frames to average
BREATH_THRESHOLD_MM = 5.0 #number of mm movement required to freeze baseline
MAX_BREATH_HOLD_FRAMES = 150 # number of frames at 30 fps
MIN_BASELINE_FRAMES = 20     # number of stable frames required to set baseline


class RealSenseBreathing:
    # Initialize camera, constructor
    def __init__(self):
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        self.config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)    
        self.depth_buffer = collections.deque(maxlen=SMOOTHING_WINDOW)
        self.baseline_depth = None
        self.frames_inhaled = 0

        self.baseline_ready = False
        self.stable_frames = 0


    # Start camera
    def start(self):
        self.pipeline.start(self.config)
        self.depth_buffer.clear()
        self.baseline_depth = None
        self.frames_inhaled = 0
        print("RealSense-kamera startad.")

    # Stop camera
    def stop(self):
        self.pipeline.stop()
        print("RealSense-kamera stoppad.")

    def _get_depth_average(self, depth_frame, roi_size=100):
        width = depth_frame.get_width()
        height = depth_frame.get_height()
        x = (width // 2) - (roi_size // 2)
        y = (height // 2) - (roi_size // 2)
        
        depth_image = np.asanyarray(depth_frame.get_data())
        roi = depth_image[y:y+roi_size, x:x+roi_size]
        valid_pixels = roi[roi > 0]
        
        if len(valid_pixels) == 0:
            return None
        return np.mean(valid_pixels)


    """ Get breathing data from radar, 
    return breath value between 0-10 based on displacement from baseline, 
    where 10 is max inhale (6mm or more) and 0 is baseline or exhale. 
    Return None if no valid data.
    """
    def get_breath_value(self):
        frames = self.pipeline.wait_for_frames()
        depth_frame = frames.get_depth_frame()
        
        if not depth_frame:
            return None

        current_dist = self._get_depth_average(depth_frame)
        if current_dist is None:
            return None

        #print(f"DEBUG raw depth: {current_dist:.1f}, baseline: {self.baseline_depth}")

        self.depth_buffer.append(current_dist)

        if len(self.depth_buffer) < SMOOTHING_WINDOW:
            return None

        smoothed_depth = sum(self.depth_buffer) / len(self.depth_buffer)


        # Smart Baseline Logic
        if self.baseline_depth is None:
            self.baseline_depth = smoothed_depth
        
        displacement = self.baseline_depth - smoothed_depth

        if displacement < 0:
            # subject in wrong distance compared to baseline, reset baseline quickly
            self.baseline_depth = (self.baseline_depth * 0.80) + (smoothed_depth * 0.20)
            displacement = 0.0
            self.frames_inhaled = 0

        if displacement < BREATH_THRESHOLD_MM:
            self.baseline_depth = (self.baseline_depth * 0.95) + (smoothed_depth * 0.05)
            self.frames_inhaled = 0
        else:
            self.frames_inhaled += 1
            if self.frames_inhaled > MAX_BREATH_HOLD_FRAMES:
                self.baseline_depth = (self.baseline_depth * 0.95) + (smoothed_depth * 0.05)

        final_displacement = max(0.0, self.baseline_depth - smoothed_depth)
        breath_value = (final_displacement / MAX_DISPLACEMENT_MM) * 10.0
        
        if abs(current_dist - self.baseline_depth) > 11.0:
            return None
        else:
            return max(0.0, min(10.0, breath_value))