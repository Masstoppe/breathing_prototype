import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

# --- KONFIGURATION ---
FILE_PATH = "../breathing_data.jsonl"
WINDOW_SIZE = 3 # Hur många andetag som ska glidande-medelvärdesbildas för en mjukare graf

def load_data(filepath):
    """Läser in jsonl-filen och returnerar en pandas DataFrame."""
    data = []
    with open(filepath, "r") as f:
        for line in f:
            # Ignorera separatorer och tomma rader
            if line.startswith("-") or not line.strip():
                continue
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                print("Kunde inte läsa rad, hoppar över...")
                continue
    
    df = pd.DataFrame(data)
    if not df.empty:
        # Normalisera tiden så att experimentet börjar på 0 sekunder
        start_time = df['timestamp'].min()
        df['relative_time'] = df['timestamp'] - start_time
    return df

def calculate_bpm_over_time(time_array, value_array, sensor_name):
    """
    Hittar andetag (peaks) i datan och beräknar BPM över tid.
    """
    # 1. Hitta toppar (inhalationer)
    # Parametern 'prominence' gör att vi bara hittar tydliga toppar och ignorerar småbrus.
    # 'distance' sätter ett minsta tidsavstånd mellan toppar (t.ex. 10 samples = 0.5s vid 20Hz)
    if sensor_name == "co2_sensor":
        # CO2 mäts i PPM, vi letar efter stora variationer
        peaks, _ = find_peaks(value_array, prominence=100, distance=15)
    else:
        # Radar och Kamera är mappade mellan 0.0 och 10.0
        peaks, _ = find_peaks(value_array, prominence=1.5, distance=15)
    
    if len(peaks) < 2:
        return [], [] # För få andetag för att beräkna BPM

    # 2. Hämta tidsstämplar för varje andetag
    peak_times = time_array.iloc[peaks].values
    
    # 3. Beräkna tiden mellan varje andetag (Inter-Breath Interval, IBI)
    ibis = np.diff(peak_times) # Avstånd i sekunder mellan andetag i och i-1
    
    # 4. Konvertera IBI till Breaths Per Minute (BPM)
    # Instantaneous BPM = 60 / sekunder per andetag
    instant_bpm = 60.0 / ibis
    
    # 5. Skapa en utjämnad kurva (Glidande medelvärde) för att grafen ska bli snyggare att läsa
    smoothed_bpm = pd.Series(instant_bpm).rolling(window=WINDOW_SIZE, min_periods=1).mean().values
    
    # Tidsaxeln för BPM blir vid varje nytt andetag
    bpm_times = peak_times[1:] 
    
    return bpm_times, smoothed_bpm

def main():
    print(f"Laddar data från {FILE_PATH}...")
    df = load_data(FILE_PATH)
    
    if df.empty:
        print("Ingen data hittades i filen.")
        return

    # Dela upp datan per sensor
    sensors = df['sensor_type'].unique()
    
    # Sätt upp grafen
    plt.figure(figsize=(12, 6))
    
    colors = {'camera': 'blue', 'radar': 'green', 'co2_sensor': 'red'}
    labels = {'camera': 'RealSense camera', 'radar': 'A121 Radar', 'co2_sensor': 'CO2'}

    for sensor in sensors:
        if sensor == "none" or pd.isna(sensor):
            continue
            
        sensor_df = df[df['sensor_type'] == sensor].copy()
        
        # Bestäm vilken kolumn som innehåller sensorns råvärde
        val_col = 'ppm' if sensor == 'co2_sensor' else 'breath_value'
        
        # Filtrera bort eventuella -99.0 värden (som är från kalibreringsfasen)
        if val_col == 'breath_value':
            sensor_df = sensor_df[sensor_df[val_col] >= 0.0]
            
        if len(sensor_df) < 50: # Behöver lite data för att kunna analysera
            print(f"För lite data för sensor: {sensor}")
            continue

        print(f"Analyserar {sensor}...")
        times, bpms = calculate_bpm_over_time(sensor_df['relative_time'], sensor_df[val_col], sensor)
        
        if len(times) > 0:
            color = colors.get(sensor, 'black')
            label = labels.get(sensor, sensor)
            # Rita upp BPM-linjen
            plt.plot(times, bpms, marker='o', markersize=4, linestyle='-', linewidth=2, color=color, label=label)

    # Formatera grafen
    plt.title("Breathing frequency over time (BPM)", fontsize=16)
    plt.xlabel("Time in the experiment (Seconds)", fontsize=12)
    plt.ylabel("Breaths per minute (BPM)", fontsize=12)
    
    # Dynamisk skalning av y-axeln beroende på normal andningshastighet (oftast 10-30 för vuxna/barn)
    plt.ylim(0,70) 
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(loc='upper right', fontsize=11)
    plt.tight_layout()
    
    # Spara grafen som en bild som du kan lägga in i din rapport
    plt.savefig("bpm_analysis_graph.png", dpi=300)
    print("Graf sparad som 'bpm_analysis_graph.png'. Visar grafen nu...")
    
    # Visa grafen på skärmen
    plt.show()

if __name__ == "__main__":
    main()