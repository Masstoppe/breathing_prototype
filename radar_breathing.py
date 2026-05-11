# Copyright (c) Acconeer AB, 2022-2025
# All rights reserved

#för att köra: python3 breathing_with_gui.py --serial-port /dev/ttyUSB0


# pyright: reportPrivateImportUsage=false

from __future__ import annotations
import collections
import acconeer.exptool as et
from acconeer.exptool import a121
from acconeer.exptool.a121.algo.breathing._processor import AppState, BreathingProcessorConfig
from acconeer.exptool.a121.algo.breathing._ref_app import RefApp
from acconeer.exptool.a121.algo.breathing._ref_app import (
    RefAppConfig,
    get_sensor_config,
)
from acconeer.exptool.a121.algo.presence._processors import ProcessorConfig as PresenceProcessorConfig
from acconeer.exptool.a121 import Client

#CONFIGURATION
MAX_DISPLACEMENT_MM = 6 # max inhale movement in millimeter 
SMOOTHING_WINDOW = 5  # number of frames to average
BREATH_THRESHOLD_MM = 5 #number of mm movement required to freeze baseline
MAX_BREATH_HOLD_FRAMES = 150 # number of frames at 30 fps


class RadarBreathing:
    #initialize radar, constructor
    def __init__(self, serial_port="/dev/ttyUSB0"): # ttyUSB0 standard but can be overwritten
        self.serial_port = serial_port
        self.sensor = 1
        
        self.breathing_processor_config = BreathingProcessorConfig(
        lowest_breathing_rate=6,
        highest_breathing_rate=60,
        time_series_length_s=20,
    )

        self.presence_config = PresenceProcessorConfig(
        intra_detection_threshold=4,
        intra_frame_time_const=0.15,
        inter_frame_fast_cutoff=20,
        inter_frame_slow_cutoff=0.2,
        inter_frame_deviation_time_const=0.5,
    )

        self.ref_app_config = RefAppConfig(
        use_presence_processor=True,
        num_distances_to_analyze=3,
        distance_determination_duration=5,
        breathing_config=self.breathing_processor_config,
        presence_config=self.presence_config,
    )
        self.sensor_config = get_sensor_config(ref_app_config=self.ref_app_config)
        self.client = None
        self.ref_app = None

        self.motion_buffer = collections.deque(maxlen=SMOOTHING_WINDOW)
        self.baseline_motion = None
        self.frames_inhaled = 0

    def start(self): # Start radar
        self.client = a121.Client.open(serial_port=self.serial_port)
        self.ref_app = RefApp(client=self.client, sensor_id=self.sensor, ref_app_config=self.ref_app_config)
        self.ref_app.start()


        self.motion_buffer.clear()
        self.baseline_motion = None
        self.frames_inhaled = 0
        print("Radar-sensor startad.")

    def stop(self): # Stop radar
        if self.ref_app:
            self.ref_app.stop()
        if self.client:
            self.client.close()
        print("Radar-sensor stoppad.")


    """ Get breathing data from radar, 
    return breath value between 0-10 based on displacement from baseline, 
    where 10 is max inhale (6mm or more) and 0 is baseline or exhale. 
    Return None if no valid data.
    """
    def get_breath_value(self):
        if not self.ref_app:
            return None

        processed_data = self.ref_app.get_next()
        app_state = processed_data.app_state

        if app_state == AppState.ESTIMATE_BREATHING_RATE:
            if processed_data.breathing_result is not None:
                extra_result = processed_data.breathing_result.extra_result
                if extra_result is not None:
                    # Radarns latest breathing motion value in mm.
                    current_motion = extra_result.breathing_motion[-1]
                    
                    self.motion_buffer.append(current_motion)
                    if len(self.motion_buffer) < SMOOTHING_WINDOW:
                        return None
                        
                    smoothed_motion = sum(self.motion_buffer) / len(self.motion_buffer) # return mean value of 10 values
                    
                    # Set first baseline if not set (smart baseline logic will update this over time)
                    if self.baseline_motion is None:
                        self.baseline_motion = smoothed_motion

                    # Calculate displacement from baseline
                    displacement = self.baseline_motion - smoothed_motion 

                    # Smart Baseline Logic:
                    if displacement < 0:
                        # subject in wrong distance compared to baseline, reset baseline quickly
                        self.baseline_motion = (self.baseline_motion * 0.80) + (smoothed_motion * 0.20)
                        displacement = 0.0
                        self.frames_inhaled = 0
                        
                    elif displacement < BREATH_THRESHOLD_MM:
                        # subject is close to baseline, update baseline slowly and reset inhale frames
                        self.baseline_motion = (self.baseline_motion * 0.95) + (smoothed_motion * 0.05)
                        self.frames_inhaled = 0
                        
                    else:
                        # subject is away from baseline, likely holding breath, do not update baseline and count up inhale frames
                        self.frames_inhaled += 1
                        if self.frames_inhaled > MAX_BREATH_HOLD_FRAMES:
                            # subject has likely been holding breath for a while, update baseline slowly to new position
                            self.baseline_motion = (self.baseline_motion * 0.95) + (smoothed_motion * 0.05)
                        else:
                            # subject is likely inhaling, do not update baseline
                            pass

                    # Calculate final breath value based on displacement, cap to 10.0
                    breath_value = (displacement / MAX_DISPLACEMENT_MM) * 10.0
                    return max(0.0, min(10.0, breath_value))
                    
        # If we are not in the right app state or don't have valid breathing data, return None
        return None

