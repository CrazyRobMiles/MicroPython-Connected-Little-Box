from managers.base_manager import CLBDeviceManager
from managers.event import Event
import machine
import time


class Manager(CLBDeviceManager):
    version = "1.0.0"

    device_default_settings = {
        "trigger_pin": 5,
        "echo_pin": 18,
        "interval_ms": 500,
        "threshold_mm": 300,
        "startup_offset_us": 450,
    }

    def __init__(self, clb):
        super().__init__(clb)
        self.events = {}
        self._trigger_pin = None
        self._echo_pin = None
        self._echo_start = 0
        self._echo_duration = 0
        self._reading_ready = False
        self._measuring = False
        self._last_trigger_ms = 0
        self._trigger_pending = False
        self._current_distance_mm = -1
        self._last_above_threshold = None  # None=unknown, True=above, False=below
        self._active = False

    def _echo_irq_handler(self, pin):
        if self._measuring:
            self._echo_duration = time.ticks_diff(time.ticks_us(), self._echo_start)
            self._reading_ready = True
            self._measuring = False

    def setup(self, settings):
        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        trigger_pin_num = self.settings.get("trigger_pin", 5)
        echo_pin_num = self.settings.get("echo_pin", 18)

        try:
            self._trigger_pin = machine.Pin(trigger_pin_num, machine.Pin.OUT)
            self._trigger_pin.value(0)

            self._echo_pin = machine.Pin(echo_pin_num, machine.Pin.IN)
            self._echo_pin.irq(
                trigger=machine.Pin.IRQ_FALLING,
                handler=self._echo_irq_handler
            )

            self.events = {
                "hcsr04.reading": Event(
                    name="hcsr04.reading",
                    description="HC-SR04 distance reading in mm",
                    owner=self
                ),
                "hcsr04.below_threshold": Event(
                    name="hcsr04.below_threshold",
                    description="Distance dropped below configured threshold",
                    owner=self
                ),
                "hcsr04.above_threshold": Event(
                    name="hcsr04.above_threshold",
                    description="Distance rose above configured threshold",
                    owner=self
                ),
                "hcsr04.timeout": Event(
                    name="hcsr04.timeout",
                    description="No echo received within 500ms of trigger pulse",
                    owner=self
                ),
            }

            self.state = self.STATE_OK
            self.set_status(7001, f"HC-SR04 ready (trigger={trigger_pin_num}, echo={echo_pin_num})")
            print(f"[hcsr04] Ready on trigger={trigger_pin_num}, echo={echo_pin_num}")
        except Exception as e:
            self.state = self.STATE_ERROR
            self.set_status(7002, f"HC-SR04 setup failed: {e}")
            print(f"[hcsr04] Setup failed: {e}")

    def _trigger_reading(self):
        self._reading_ready = False
        self._trigger_pin.value(1)
        time.sleep_us(10)
        self._trigger_pin.value(0)
        self._echo_start = time.ticks_us()
        self._measuring = True
        self._last_trigger_ms = time.ticks_ms()
        self._trigger_pending = True

    def update(self):
        if not self.enabled or self.state != self.STATE_OK or not self._active:
            return

        interval_ms = self.settings.get("interval_ms", 500)
        threshold_mm = self.settings.get("threshold_mm", 300)
        now = time.ticks_ms()

        # Timeout stale measurement (HC-SR04 max echo is ~38ms)
        if self._measuring:
            if time.ticks_diff(now, self._last_trigger_ms) > 50:
                self._measuring = False

        # Fire timeout event if no echo received within 500ms of the trigger pulse
        if self._trigger_pending and not self._reading_ready:
            if time.ticks_diff(now, self._last_trigger_ms) > 500:
                self._trigger_pending = False
                self._measuring = False
                self.events["hcsr04.timeout"].publish({
                    "last_trigger_ms": self._last_trigger_ms
                })

        # Trigger a new reading when interval has elapsed and no measurement in flight
        if not self._measuring and not self._reading_ready and not self._trigger_pending:
            if time.ticks_diff(now, self._last_trigger_ms) >= interval_ms:
                self._trigger_reading()
                return

        # Process a completed reading — discard spurious IRQ firings after _trigger_pending cleared
        if self._reading_ready:
            self._reading_ready = False
            if not self._trigger_pending:
                return
            self._trigger_pending = False
            startup_offset_us = self.settings.get("startup_offset_us", 450)
            duration_us = max(0, self._echo_duration - startup_offset_us)
            distance_mm = (duration_us * 343) // 2000
            self._current_distance_mm = distance_mm

            self.events["hcsr04.reading"].publish({
                "distance_mm": distance_mm,
                "duration_us": duration_us
            })

            above = distance_mm > threshold_mm
            if self._last_above_threshold is None:
                self._last_above_threshold = above
            elif above and not self._last_above_threshold:
                self._last_above_threshold = True
                self.events["hcsr04.above_threshold"].publish({
                    "distance_mm": distance_mm,
                    "threshold_mm": threshold_mm
                })
            elif not above and self._last_above_threshold:
                self._last_above_threshold = False
                self.events["hcsr04.below_threshold"].publish({
                    "distance_mm": distance_mm,
                    "threshold_mm": threshold_mm
                })

    def command_start(self):
        """Start taking distance readings."""
        self._active = True
        self._last_trigger_ms = 0  # trigger immediately on next update
        self._trigger_pending = False
        self._last_above_threshold = None
        self._reading_ready = False
        self._measuring = False
        print("[hcsr04] Started")

    def command_stop(self):
        """Stop taking distance readings."""
        self._active = False
        print("[hcsr04] Stopped")

    def command_reading(self):
        """Get the most recent distance reading in millimetres."""
        if self._current_distance_mm < 0:
            print("[hcsr04] No reading available yet")
        else:
            print(f"[hcsr04] Distance: {self._current_distance_mm}mm")
        return self._current_distance_mm

    def command_set_interval(self, interval_ms):
        """Set the reading interval in milliseconds."""
        try:
            ms = int(interval_ms)
            self.settings["interval_ms"] = ms
            print(f"[hcsr04] Interval set to {ms}ms")
        except Exception as e:
            print(f"[hcsr04] Invalid interval: {e}")

    def command_set_threshold(self, threshold_mm):
        """Set the distance threshold in millimetres."""
        try:
            mm = int(threshold_mm)
            self.settings["threshold_mm"] = mm
            self._last_above_threshold = None  # re-detect crossing against new value
            print(f"[hcsr04] Threshold set to {mm}mm")
        except Exception as e:
            print(f"[hcsr04] Invalid threshold: {e}")

    def get_interface(self):
        return {
            "start": ("Start distance readings: start()", self.command_start),
            "stop": ("Stop distance readings: stop()", self.command_stop),
            "reading": ("Get last distance in mm: reading()", self.command_reading),
            "set_interval": ("Set reading interval in ms: set_interval(ms)", self.command_set_interval),
            "set_threshold": ("Set distance threshold in mm: set_threshold(mm)", self.command_set_threshold),
        }

    def get_published_events(self):
        return [
            {"name": "hcsr04.reading", "description": "Distance reading in mm"},
            {"name": "hcsr04.below_threshold", "description": "Distance dropped below threshold"},
            {"name": "hcsr04.above_threshold", "description": "Distance rose above threshold"},
            {"name": "hcsr04.timeout", "description": "No echo received within 500ms of trigger pulse"},
        ]

    def teardown(self):
        self._active = False
        if self._echo_pin:
            try:
                self._echo_pin.irq(handler=None)
            except Exception:
                pass
        self.set_status(7003, "HC-SR04 torn down")
