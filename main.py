#!/usr/bin/env python3
# type: ignore
import time
import sys
import subprocess
import os
import co2_sensor
import br_realsense
import radar_breathing
import paho.mqtt.client as mqtt
import json 
import threading
import queue
from threading import Event

# Event signals
mypas_active = Event()     # True when mypas_start is active

# local host
MQTT_BROKER = "localhost"

 # topics that the raspberry publishes
MQTT_TOPIC_TEST = "godot/test" #only for test purposes
MQTT_TOPIC_CO2 = "raspberry/co2"
MQTT_TOPIC_NON_CONTACT = "raspberry/non_contact"

# topics that the raspberry subscribes to
MQTT_TOPIC_MASKMODE = "godot/maskmode"
MQTT_TOPIC_CAMERAMODE = "godot/cameramode"
MQTT_TOPIC_RADARMODE = "godot/radarmode"
MQTT_TOPIC_GAMESTATUS = "godot/gamestatus"
MQTT_TOPIC_MYPAS = "godot/mypas"

# send data only once every 50 millisecond
PUBLISH_INTERVAL = 0.05

# globala variabler
write_queue = queue.Queue()
mask_mode = False
camera_mode = False
radar_mode = False
game_running = None
game_process = None
client = None
co2 = None
radar = None
camera = None
writer_thread = None

def setup_MQTT_client():
	global client
	# setup broker
	client = mqtt.Client()
	try:
		client.connect(MQTT_BROKER, 1883, 60)
		client.loop_start()
		print(f"Connected to MQTT Broker at {MQTT_BROKER}")
	except Exception as e:
		print(f"Failed to connect to MQTT broker: {e}")
		sys.exit(1)
	# setup subscription
	# activate callback
	client.on_message = on_message
	# activate subscription of the topics
	client.subscribe(MQTT_TOPIC_MASKMODE)
	client.subscribe(MQTT_TOPIC_CAMERAMODE)
	client.subscribe(MQTT_TOPIC_RADARMODE)
	client.subscribe(MQTT_TOPIC_GAMESTATUS)
	client.subscribe(MQTT_TOPIC_MYPAS)
	print("MQTT subcription initialized")

# callback when a message is received
def on_message(client, userdata, msg):
	global game_running, mask_mode, radar_mode, camera_mode
	payload = msg.payload.decode()
	topic = msg.topic

	if topic == MQTT_TOPIC_GAMESTATUS and payload == "exit":
		game_running = False
	if topic == MQTT_TOPIC_GAMESTATUS and payload == "game_running":
		game_running = True	
	if topic == MQTT_TOPIC_MASKMODE and payload == "mask_on":
		mask_mode = True
	if topic == MQTT_TOPIC_MASKMODE and payload == "mask_off":
		mask_mode = False
	if topic == MQTT_TOPIC_RADARMODE and payload == "radar_on":
		radar_mode = True
	if topic == MQTT_TOPIC_RADARMODE and payload == "radar_off":
		radar_mode = False	
	if topic == MQTT_TOPIC_CAMERAMODE and payload == "camera_on":
		camera_mode = True
	if topic == MQTT_TOPIC_CAMERAMODE and payload == "camera_off":
		camera_mode = False		
	if topic == MQTT_TOPIC_MYPAS and payload == "mypas_start":
		mypas_active.set()
		write_queue.put("separator")
	if topic == MQTT_TOPIC_MYPAS and payload == "mypas_stop":
		mypas_active.clear()


def start_game():
	global game_process
	my_env = os.environ.copy()
	my_env["DISPLAY"] = ":0"
	my_env["MESA_DEBUG"] = "silent"
	game_process = subprocess.Popen(
		["./breathing_game/breathing_gamev11.arm64", "--fullscreen"],
		env=my_env,
		stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
	)
	print("Game process started.")
	

def game_stopped():
	global game_process, co2, camera, radar, writer_thread
	if co2:
		co2.close()
	write_queue.put(None)
	writer_thread.join(timeout=3)
	# stop game
	if game_process and game_process.poll() is None:
		game_process.terminate()
		time.sleep(1)
		if game_process.poll() is None:
			game_process.kill()
			time.sleep(1)
	print("Game process stopped.")
    # shut down raspberry
	# os.system("sudo shutdown -h now")

def file_writer():
    with open("breathing_data.jsonl", "a") as f:
        last_flush = time.time()
        while True:
            line = write_queue.get()
            if line is None:
                f.flush()  # Flush vid ren avslutning
                break
            if line == "separator":
                f.write("\n-------------------------------------------------------\n")
            else:
                f.write(line + "\n")
            
            now = time.time()
            if now - last_flush >= 1.0:
                f.flush()
                last_flush = now


def run_non_contact_br():
	global client, radar, camera

	# send data only once every 50 millisecond
	last_publish_time = 0

	camera_started = False  
	radar_started = False
	try:
		if camera_mode and camera:
			camera.start()
			camera_started = True
		if radar_mode and radar:
			radar.start()
			radar_started = True

		while game_running and not mask_mode:
			final_breath_value = -99.0
			sensor_used = "none"
			if camera_mode:
				val = camera.get_breath_value()
				if val is not None:
					# only camera works
					final_breath_value = val
					sensor_used = "camera"
			if radar_mode:
				val = radar.get_breath_value()
				if val is not None:
					# only radar works
					final_breath_value = val
					sensor_used = "radar"
			
			current_time = time.time()
			if (current_time - last_publish_time) >= PUBLISH_INTERVAL:
				payload_dict = {
					"timestamp": current_time,
					"sensor_type": sensor_used,
					"breath_value": float(final_breath_value),
    			}
				payload_str = json.dumps(payload_dict)
				client.publish(MQTT_TOPIC_NON_CONTACT, payload=str(final_breath_value))
				last_publish_time = current_time
				print(f"Data: {payload_str:<60}", end='\r')
				
				# Save to .tex fil if mypas-timer är aktiv
				if mypas_active.is_set():
					write_queue.put(payload_str)


	except Exception as e:
		print(f"\nerror starting non-contact: {e}")	
	finally:
		print("\nAvslutar Non-Contact Mode...")
		if camera_started: camera.stop()
		if radar_started: radar.stop()
	
				
def run_contact_br():
	global client, co2
	last_publish_time = 0
	sensor_used = None
	try:
		while game_running and mask_mode and not camera_mode and not radar_mode:
			ppm = co2.read_co2()
			if ppm != -1:
				sensor_used = "co2_sensor"
				current_time = time.time()
				if (current_time - last_publish_time) >= PUBLISH_INTERVAL:
					payload_dict = {
						"timestamp": current_time,
						"ppm": ppm,
						"sensor_type": sensor_used
					}
					payload_str = json.dumps(payload_dict)
					print(f"CO2: {ppm} ppm")
					client.publish(MQTT_TOPIC_CO2, payload=str(ppm))
					last_publish_time = current_time
					print(f"Data: {payload_str:<60}", end='\r')

					# Spara till .tex fil om mypas-timer är aktiv
					if mypas_active.is_set():
						write_queue.put(payload_str)

	except Exception as e:
		print(f"\nerror starting contact: {e}")
	finally:
		print("Avslutar mask mode...")

def main():
	global game_running, mask_mode, camera, radar, co2, writer_thread
	writer_thread = threading.Thread(target=file_writer, daemon=True)
	writer_thread.start()
	setup_MQTT_client()

	try:
		co2 = co2_sensor.Sprintir_co2()
	except RuntimeError as e:
		print(f"Error starting co2 sensor: {e}")
		co2 = None

	try:
		camera = br_realsense.RealSenseBreathing()
	except RuntimeError as e:
		print(f"Error starting camera: {e}")
		camera = None

	try:
		radar = radar_breathing.RadarBreathing(serial_port="/dev/ttyUSB0")
	except RuntimeError as e:
		print(f"Error starting radar: {e}")
		radar = None

	start_game()
	while True:
		if game_running == True:
			if radar_mode or camera_mode:
				run_non_contact_br()
			elif mask_mode:
				run_contact_br()
			else:
				time.sleep(0.5)

		if game_running == False:	
			game_stopped()
			break	

		elif game_running == None:
			time.sleep(0.5)

if __name__ == "__main__":
	main()