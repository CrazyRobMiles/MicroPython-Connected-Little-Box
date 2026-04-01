# /managers/display_manager.py
from managers.base_manager import CLBManager
from managers.event import Event
from graphics.display_devices import GFX_LCDDisplay, DisplayItem
import sys
import struct

# The person sensor has the I2C ID of hex 62, or decimal 98.
PERSON_SENSOR_I2C_ADDRESS = 0x62

# We will be reading raw bytes over I2C, and we'll need to decode them into
# data structures. These strings define the format used for the decoding, and
# are derived from the layouts defined in the developer guide.
PERSON_SENSOR_I2C_HEADER_FORMAT = "BBH"
PERSON_SENSOR_I2C_HEADER_BYTE_COUNT = struct.calcsize(
    PERSON_SENSOR_I2C_HEADER_FORMAT)

PERSON_SENSOR_FACE_FORMAT = "BBBBBBbB"
PERSON_SENSOR_FACE_BYTE_COUNT = struct.calcsize(PERSON_SENSOR_FACE_FORMAT)

PERSON_SENSOR_FACE_MAX = 4
PERSON_SENSOR_RESULT_FORMAT = PERSON_SENSOR_I2C_HEADER_FORMAT + \
    "B" + PERSON_SENSOR_FACE_FORMAT * PERSON_SENSOR_FACE_MAX + "H"
PERSON_SENSOR_RESULT_BYTE_COUNT = struct.calcsize(PERSON_SENSOR_RESULT_FORMAT)

# How long to pause between sensor polls.
PERSON_SENSOR_DELAY = 0.2

class PersonSensor():
    def __init__(self, i2c):
        self.i2c = i2c
    
    def get_faces(self):
        
        while not i2c.try_lock():
            pass
        
        read_data = bytearray(PERSON_SENSOR_RESULT_BYTE_COUNT)
        self.i2c.readfrom_into(PERSON_SENSOR_I2C_ADDRESS, read_data)
        self.i2c.unlock()

        offset = 0
        (pad1, pad2, payload_bytes) = struct.unpack_from(
            PERSON_SENSOR_I2C_HEADER_FORMAT, read_data, offset)
        offset = offset + PERSON_SENSOR_I2C_HEADER_BYTE_COUNT

        (num_faces) = struct.unpack_from("B", read_data, offset)
        num_faces = int(num_faces[0])
        offset = offset + 1

        faces = []
        for i in range(num_faces):
            (box_confidence, box_left, box_top, box_right, box_bottom, id_confidence, id,
             is_facing) = struct.unpack_from(PERSON_SENSOR_FACE_FORMAT, read_data, offset)
            offset = offset + PERSON_SENSOR_FACE_BYTE_COUNT
            face = {
                "box_confidence": box_confidence,
                "box_left": box_left,
                "box_top": box_top,
                "box_right": box_right,
                "box_bottom": box_bottom,
                "id_confidence": id_confidence,
                "id": id,
                "is_facing": is_facing,
            }
            faces.append(face)
        checksum = struct.unpack_from("H", read_data, offset)
        return faces
        

class Manager(CLBManager):
    version = "1.0.2"

    STATE_DISABLED = "disabled"
    STATE_IDLE     = "idle"

    def __init__(self, clb):
        super().__init__(clb, defaults={
            "active":True,
            "sensitivity":5
        })
        self.state = self.STATE_IDLE
        self.personSensor = None

    # ---------------------------------------------------------------------
    # SETUP
    # ---------------------------------------------------------------------
    def setup(self, settings):
        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return


    # ---------------------------------------------------------------------
    # COMMAND INTERFACE
    # ---------------------------------------------------------------------
    def get_interface(self):
        return {
            "start": ("Start tracking", self.cmd_start),
            "stop":  ("Stop stop", self.cmd_stop),
        }

    def cmd_start(self):
        self.start()

    def cmd_stop(self):
        self.stop()
