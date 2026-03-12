# /managers/blink_manager.py
from managers.base_manager import CLBManager
import machine
import time


class Manager(CLBManager):
    version = "1.0.2"

    STATE_DISABLED = "disabled"
    STATE_IDLE     = "idle"

    def __init__(self, clb):
        super().__init__(clb, defaults={
        "enabled": True,
        "uart_id":"1",
        "rx_pin": "4",
        "tx_pin": "5",
        "volume": "17",
        "dependencies": []        })
        self.state = self.STATE_IDLE

    # ---------------------------------------------------------------------
    # SETUP
    # ---------------------------------------------------------------------
    def setup(self, settings):
        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        try:
            tx_pin = int(self.settings["tx_pin"])
            rx_pin = int(self.settings["rx_pin"])
            uart_id = int(self.settings["uart_id"])
            self.volume= int(self.settings["volume"])
            self.df = DFPlayer(uart_id=uart_id, tx_pin=tx_pin, rx_pin=rx_pin)
            self.df.reset()
            self.df.set_source_tf()
            print("Volume loaded as:",self.volume)
            self.set_status(6001, f"DfPlayer manager OK")

        except Exception as e:
            self.state = self.STATE_DISABLED
            self.set_status(6002, f"DfPlayer setup error: {e}")

    # ---------------------------------------------------------------------
    # UPDATE LOOP
    # ---------------------------------------------------------------------
    def update(self):
        if not self.enabled:
            return


    # ---------------------------------------------------------------------
    # TEARDOWN
    # ---------------------------------------------------------------------
    def teardown(self):
        self.stop()
        self.set_status(6005, "DfPlayer manager torn down")

    # ---------------------------------------------------------------------
    # COMMAND INTERFACE
    # ---------------------------------------------------------------------
    def get_interface(self):
        return {
            "play": ("Play track n", self.play_track),
            "stop": ("Stop playback", self.stop),
            "volume": ("Set volume (0-30)", self.set_volume)
        }

    def play_track(self,track_no):
        print(f"Playing track:{track_no}")
        self.df.play_track(track_no)
        time.sleep_ms(30)
        self.volume= int(self.settings["volume"])
        self.set_volume(self.volume)
        time.sleep_ms(30)
        self.df.eq(DFPlayer.EQ_BASS)
        
    def stop(self):
        self.df.stop()
        
    def set_volume(self,volume):
        print(f"Setting volume to {volume}")
        self.df.volume(volume)

from machine import UART, Pin
import time

class DFPlayer:
    # DFPlayer protocol constants
    _START = 0x7E
    _VERSION = 0xFF
    _LEN = 0x06
    _END = 0xEF

    # Commands (subset)
    CMD_NEXT = 0x01
    CMD_PREV = 0x02
    CMD_PLAY_TRACK = 0x03           # play track number (1..)
    CMD_VOLUME_UP = 0x04
    CMD_VOLUME_DOWN = 0x05
    CMD_SET_VOLUME = 0x06           # 0..30
    CMD_SET_EQ = 0x07               # 0..5
    CMD_SET_PLAYBACK_SRC = 0x09     # 0x01 U-disk, 0x02 TF, 0x03 AUX, etc.
    CMD_SLEEP = 0x0A
    CMD_RESET = 0x0C
    CMD_PLAY = 0x0D
    CMD_PAUSE = 0x0E
    CMD_PLAY_FOLDER_FILE = 0x0F     # folder, file
    CMD_STOP = 0x16
    CMD_LOOP_TRACK = 0x19
    CMD_SET_DAC = 0x1A              # 0/1
    CMD_QUERY_STATUS = 0x42
    CMD_QUERY_VOLUME = 0x43
    CMD_QUERY_EQ = 0x44
    CMD_QUERY_FILECOUNT_TF = 0x48
    CMD_QUERY_CUR_TRACK = 0x4C

    # EQ values
    EQ_NORMAL = 0
    EQ_POP = 1
    EQ_ROCK = 2
    EQ_JAZZ = 3
    EQ_CLASSIC = 4
    EQ_BASS = 5

    # Playback source values (common)
    SRC_USB = 0x01
    SRC_TF  = 0x02

    def __init__(self, uart_id=0, tx_pin=0, rx_pin=1, baudrate=9600, timeout_ms=200):
        self.uart = UART(
            uart_id,
            baudrate=baudrate,
            tx=Pin(tx_pin),
            rx=Pin(rx_pin),
            timeout=timeout_ms
        )
        # Small settle time
        time.sleep_ms(200)

    def _checksum(self, cmd, param1, param2):
        # checksum is 16-bit: -(version + len + cmd + feedback + param1 + param2)
        s = self._VERSION + self._LEN + cmd + 0x00 + param1 + param2
        chk = (-s) & 0xFFFF
        return (chk >> 8) & 0xFF, chk & 0xFF

    def _send(self, cmd, value=0, feedback=False):
        # value is 16-bit
        param1 = (value >> 8) & 0xFF
        param2 = value & 0xFF
        fb = 0x01 if feedback else 0x00
        chk1, chk2 = self._checksum(cmd, param1, param2)

        frame = bytes([
            self._START,
            self._VERSION,
            self._LEN,
            cmd,
            fb,
            param1,
            param2,
            chk1,
            chk2,
            self._END
        ])
        
        print("DF SEND:", " ".join(f"{b:02X}" for b in frame))
        
        self.uart.write(frame)

    def _read_frame(self, timeout_ms=300):
        # DFPlayer responses are also 10 bytes (often). We'll wait for start byte then read 9 more.
        t0 = time.ticks_ms()
        buf = bytearray()

        while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
            if self.uart.any():
                b = self.uart.read(1)
                if not b:
                    continue
                if not buf:
                    if b[0] != self._START:
                        continue
                buf += b
                if len(buf) == 10:
                    return bytes(buf)
            time.sleep_ms(2)
        return None

    def reset(self):
        self._send(self.CMD_RESET)
        time.sleep_ms(1000)

    def set_source_tf(self):
        self._send(self.CMD_SET_PLAYBACK_SRC, self.SRC_TF)
        time.sleep_ms(200)

    def volume(self, v=None):
        if v is None:
            self._send(self.CMD_QUERY_VOLUME, feedback=False)
            f = self._read_frame()
            return self._parse_response_value(f)
        v = max(0, min(30, int(v)))
        self._send(self.CMD_SET_VOLUME, v)

    def eq(self, mode):
        mode = max(0, min(5, int(mode)))
        self._send(self.CMD_SET_EQ, mode)

    def play(self):
        self._send(self.CMD_PLAY)

    def pause(self):
        self._send(self.CMD_PAUSE)

    def stop(self):
        self._send(self.CMD_STOP)

    def next(self):
        self._send(self.CMD_NEXT)

    def prev(self):
        self._send(self.CMD_PREV)

    def play_track(self, n):
        # n = 1..9999 depending on card naming/indexing
        self._send(self.CMD_PLAY_TRACK, int(n))

    def loop_track(self, n):
        self._send(self.CMD_LOOP_TRACK, int(n))

    def play_folder_file(self, folder, file):
        # folder: 1..99, file: 1..255 (depends on DFPlayer rules)
        folder = max(1, min(99, int(folder)))
        file = max(1, min(255, int(file)))
        value = (folder << 8) | file
        self._send(self.CMD_PLAY_FOLDER_FILE, value)

    def status(self):
        self._send(self.CMD_QUERY_STATUS, feedback=True)
        f = self._read_frame()
        return self._parse_response_value(f)

    def current_track(self):
        self._send(self.CMD_QUERY_CUR_TRACK, feedback=True)
        f = self._read_frame()
        return self._parse_response_value(f)

    def filecount_tf(self):
        self._send(self.CMD_QUERY_FILECOUNT_TF, feedback=True)
        f = self._read_frame()
        return self._parse_response_value(f)

    def _parse_response_value(self, frame):
        # Typical response frame:
        # 7E FF 06 <cmd> <fb> <hi> <lo> <chk_hi> <chk_lo> EF
        if not frame or len(frame) != 10 or frame[0] != self._START or frame[-1] != self._END:
            return None
        hi = frame[5]
        lo = frame[6]
        return (hi << 8) | lo

