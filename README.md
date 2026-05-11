
## Project Overview

This project monitors breathing rate using camera, radar and CO2 sensor and uses it as a controller for a game:
- **RealSense 435I Camera** -  breathing detection
- **Acconeer A121 Radar** - Radar-based breathing analysis
- **SprintIR-R CO2 Sensor** - Air quality measurement
- **MQTT** - Communication with Godot game
- **Godot 4.6.1 - Game engine used to develop the breathing game

## HOW TO USE

### 1. Create virtual environment
```bash
python3 -m venv env
source env/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

## System Requirements
- Python 3.13 or later
- Raspberry Pi 5 (recommended for Arm64)
- RealSense 435I camera (USB 3.0)
- Acconeer A121 radar sensor module (USB 3.0)
- SprintIR-R CO2 Sensor (UART communication)

## Usage

### Start main program
```bash
python3 main.py
```

The program runs the following sensor modules:
- `br_realsense.py` - RealSense breathing detector
- `radar_breathing.py` - Radar breathing analysis
- `co2_sensor.py` - CO2 measurement

### Data Analysis
To analyze saved data:
```bash
python3 data_analysis/analyze_breathing.py
```

Data is saved in `breathing_data.jsonl` format.

## MQTT Topics

The program publishes/subscribes to the following MQTT topics:

**Publisher (from Raspberry):**
- `raspberry/co2` - CO2 values in PPM
- `raspberry/non_contact` - Breathing data from sensors

**Subscriber (from Godot):**
- `godot/maskmode` - Mask mode
- `godot/cameramode` - Camera mode
- `godot/radarmode` - Radar mode
- `godot/gamestatus` - Game status
- `godot/mypas` - data colleciton command (called mypas because mYPAS behavioral checklist was the initialy indented to be used when this command got receieved)

## Configuration

### RealSense 435I Camera

**Hardware Settings:**
- Resolution: 640 × 480 pixels
- Frame rate: 30 FPS
- Depth format: Z16 (16-bit depth)
- USB: 3.0 (minimum 5 Gbps bandwidth)

**Breathing Detection Parameters:**
- **Max displacement threshold**: 6.0 mm (maximum inhalation movement)
- **Movement threshold**: 5.0 mm (number of mm movement required to freeze baseline)
- **Smoothing window**: 10 frames (rolling average window)
- **Max breath hold frames**: 150 frames (~5 seconds at 30 FPS)
- **Min baseline frames**: 20 frames (stable frames required to establish baseline)

**ROI (Region of Interest):**
- Size: 100 × 100 pixels (center of image)
- Position: Center of depth frame
- Purpose: Reduces noise by focusing on chest/torso area

**Baseline Calibration:**
- Dynamic baseline adjustment with decay factor (0.95 for drift correction)
- Quick baseline reset (0.80 factor) when subject moves beyond expected range
- Displacement calculation: baseline_depth - smoothed_depth

### Acconeer A121 Radar Sensor

**Hardware Settings:**
- Interface: USB 3.0 (via XC120 module)
- Serial port: `/dev/ttyUSB0` (default, configurable)
- Sensor ID: 1

**Breathing Detection Configuration:**
- **Breathing rate range**: 6-60 BPM
- **Time series length**: 20 seconds
- **Smoothing window**: 5 frames
- **Max displacement**: 6 mm
- **Breath threshold**: 5 mm
- **Max breath hold frames**: 150 frames

**Presence Detection Configuration:**
- **Intra-detection threshold**: 4
- **Intra-frame time constant**: 0.15 seconds
- **Inter-frame fast cutoff**: 20 Hz
- **Inter-frame slow cutoff**: 0.2 Hz
- **Deviation time constant**: 0.5 seconds

**Distance Analysis:**
- **Distances to analyze**: 3 ranges
- **Distance determination duration**: 5 seconds
- **Purpose**: Adaptive range detection for variable subject distance

### SprintIR-R CO2 Sensor

**Serial Communication:**
- **Port**: `/dev/serial0` (UART on Raspberry Pi GPIO pins)
- **Baudrate**: 38400 bps
- **Data format**: ASCII
- **Stop bits**: 1
- **Data bits**: 8
- **Parity**: None

**Data Format:**
- Output format: "Z [PPM_VALUE]\r\n"
- Example: "Z 412\r\n" (412 ppm CO2)

**Commands:**
- **Read CO2**: Continuous stream (automatic at ~1 Hz)
- **Zero calibration**: Command "G" to calibrate in fresh air (400 ppm)

## Troubleshooting

### RealSense camera not connecting
```bash
# Check USB connection and drivers
rs-enumerate-devices
```

### Radar sensor not connecting
Check serial port:
```bash
ls /dev/ttyUSB*
```

### MQTT connection failed
Ensure MQTT broker is running on localhost:1883
```bash
mosquitto -v
```
