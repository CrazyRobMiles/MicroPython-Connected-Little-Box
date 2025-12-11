# device_configurator.py
version = "1.0.0"
import time
import json
import os
from machine import Pin
import sys

try:
    from machine import unique_id
    uid_bytes = unique_id()
    print("Machine Unique ID set")
except:
    print("Used default ID")
    uid_bytes = b'\x01\x02\x03\x04\x05\x06\x07\x08'

MAGIC = b'\xDE\xAD\xBE\xEF'

class DeviceConfigurator:
    def __init__(
        self,
        settings_file,
        safe_pin,
        use_obfuscation,
    ):
        self.settings = {}
        self.settings_file = settings_file
        self.safe_pin = safe_pin
        self.use_obfuscation = use_obfuscation

    def file_exists(self):
        try:
            os.stat(self.settings_file)
            return True
        except OSError:
            return False

    def _prng(self, seed):
        state = seed
        while True:
            state = (state * 1103515245 + 12345) & 0x7FFFFFFF
            yield state & 0xFF

    def _xor_data(self, data, seed):
        rng = self._prng(seed)
        return bytes([b ^ next(rng) for b in data])

    def load(self):
        try:
            with open(self.settings_file, "rb" if self.use_obfuscation else "r") as f:
                data = f.read()

            if self.use_obfuscation:
                if data[:4] != MAGIC:
                    raise ValueError("Invalid magic header")
                obfuscated = data[4:]
                seed = sum(uid_bytes)
                json_bytes = self._xor_data(obfuscated, seed)
                self.settings = json.loads(json_bytes.decode("utf-8"))
            else:
                self.settings = json.loads(data)
            return True
        except Exception as e:
            return False

    def save(self):
        try:
            if self.use_obfuscation:
                json_bytes = json.dumps(self.settings).encode("utf-8")
                seed = sum(uid_bytes)
                obfuscated = self._xor_data(json_bytes, seed)
                with open(self.settings_file, "wb") as f:
                    f.write(MAGIC + obfuscated)
            else:
                with open(self.settings_file, "w") as f:
                    json.dump(self.settings, f)
            return True
        except Exception as e:
            raise e

    def wait_for_settings(self):
        while True:
            try:
                line = sys.stdin.readline().strip()
                print("got a line")
                if line == "GET":
                    print((json.dumps(self.settings) + "\n").encode("utf-8"))
                    continue
                if line.startswith("{"):
                    self.settings.clear()
                    self.settings.update(json.loads(line))
                    self.save()
                    return True
            except Exception as e:
                print("Serial error:", e)
                return False
            time.sleep(0.1)

    def setup(self,force_online=False):
      
        if(self.safe_pin>0):
            pin = Pin(self.safe_pin, Pin.IN, Pin.PULL_UP)
            safe_pin_value = pin.value
        else:
            safe_pin_value=True
        
        # pin is pulled low if a button is pressed
        
        if not safe_pin_value or force_online:
            print("Entering setup mode")
            return self.wait_for_settings()

        if self.file_exists():
            try:
                if self.load():
                    print("Settings loaded")
                    return True
            except Exception as e:
                print("Error loading settings:", e)
        else:
            print("Settings file not found")
        
        return False


