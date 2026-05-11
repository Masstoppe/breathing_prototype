# type: ignore
import serial
import time
import sys


SERIAL_PORT = "/dev/serial0"
BAUD_RATE = 38400


class Sprintir_co2:
    # Initialize co2 sensor, contructor
    def __init__(self, port=SERIAL_PORT, baud_rate = BAUD_RATE):
        self.port = port
        self.baud_rate = baud_rate
        self.ser = None
        self._connect()

    def _connect(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=None
            )
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except serial.SerialException as e:
            raise RuntimeError(f"Unable to open UART: {e}")
        
    def read_co2(self):
        line = self.ser.readline() 
        try:
            # Decode byte string containing CO2 data and remove \r\n
            line_str = line.decode('ascii').strip()
            if line_str.startswith("Z "):
                parts = line_str.split()
                if len(parts) >= 2 and parts[0] == 'Z':
                    ppm = int(parts[1])
                    return ppm
        except (ValueError, UnicodeDecodeError, IndexError):
            # if data is trash, do nothing
            pass  
        return -1
     
        
    def zero_in_fresh_air(self):
        return self._send_command("G")
    
    def _send_command(self, command):
        full_command = f"{command}\r\n"
        try:
            self.ser.write(full_command.encode('ascii'))
            return 0
        except Exception:
         return -1
    
    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        
