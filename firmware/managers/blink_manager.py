# /managers/blink_manager.py
from managers.base import CLBManager
import machine
import time


class Manager(CLBManager):
    version = "1.0.2"
    dependencies = []  # Nothing depends on blink yet

    STATE_DISABLED = "disabled"
    STATE_IDLE     = "idle"

    def __init__(self, clb):
        super().__init__(clb, defaults={
            "pin": "LED",
            "delay_seconds": 1.0,
        })
        self.state = self.STATE_IDLE
        self._gen  = None
        self.led   = None

    # ---------------------------------------------------------------------
    # SETUP
    # ---------------------------------------------------------------------
    def setup(self, settings):
        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        try:
            pin_setting = self.settings["pin"]
            self.delay = float(self.settings["delay_seconds"])

            # Accept "LED" or a GPIO number
            if isinstance(pin_setting, str):
                self.led = machine.Pin(pin_setting, machine.Pin.OUT)
            else:
                self.led = machine.Pin(int(pin_setting), machine.Pin.OUT)

            self.led.value(0)

            self.state = self.STATE_OK
            self.set_status(6001, f"Blink manager OK on pin {pin_setting}")

        except Exception as e:
            self.state = self.STATE_DISABLED
            self.set_status(6002, f"Blink setup error: {e}")

    # ---------------------------------------------------------------------
    # BLINK COROUTINE
    # ---------------------------------------------------------------------
    def _blink_coroutine(self):
        delay_ms = int(self.delay * 1000)

        while True:
            self.led.value(1)
            start = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), start) < delay_ms:
                yield

            self.led.value(0)
            start = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), start) < delay_ms:
                yield

    # ---------------------------------------------------------------------
    # START / STOP
    # ---------------------------------------------------------------------
    def start(self):
        self._gen = self._blink_coroutine()
        self.state = self.STATE_OK       # still OK
        self.set_status(6003, "Blink started")

    def stop(self):
        self._gen = None
        if self.led:
            self.led.value(0)
        self.state = self.STATE_OK       # still OK
        self.set_status(6004, "Blink stopped")

    # ---------------------------------------------------------------------
    # UPDATE LOOP
    # ---------------------------------------------------------------------
    def update(self):
        if not self.enabled:
            return

        if self._gen:
            try:
                next(self._gen)
            except StopIteration:
                self._gen = None
                self.state = self.STATE_OK

    # ---------------------------------------------------------------------
    # TEARDOWN
    # ---------------------------------------------------------------------
    def teardown(self):
        if self.led:
            self.led.value(0)
        self.set_status(6005, "Blink manager torn down")

    # ---------------------------------------------------------------------
    # COMMAND INTERFACE
    # ---------------------------------------------------------------------
    def get_interface(self):
        return {
            "start": ("Start blinking", self.cmd_start),
            "stop":  ("Stop blinking", self.cmd_stop),
        }

    def cmd_start(self):
        self.start()

    def cmd_stop(self):
        self.stop()
