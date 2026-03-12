from managers.base_manager import CLBManager
from managers.event import Event
import time


class Manager(CLBManager):
    version = "1.1.0"

    def __init__(self, clb):
        super().__init__(clb, defaults={
            "src_gpio": "tilt",          # expects gpio.tilt_high / gpio.tilt_low
            "rest_calibrate_ms": 2000,   # latch rest state after this long with no transitions

            "hold_ms": 700,              # tipped fires after this long away from rest
            "pulse_min_ms": 150,
            "pulse_max_ms": 2500,
            "long_ms": 1000,

            "max_intertap_ms": 700,      # max gap between pulse ENDS for same sequence
            "end_gap_ms": 800,           # publish sequence after this gap since last pulse end
        })

        self.event_manager = None
        self.events = {}

        # config
        self.src_gpio = "tilt"
        self.name = "clock"
        self.rest_calibrate_ms = 2000
        self.hold_ms = 700
        self.pulse_min_ms = 150
        self.pulse_max_ms = 2500
        self.long_ms = 1000
        self.max_intertap_ms = 700
        self.end_gap_ms = 800

        # debounced state inferred from events
        self.state_known = False
        self.current_state = 0

        # rest state calibration
        self.rest_latched = False
        self.rest_state = 0
        self.last_transition_ms = 0  # used for “quiet period” tests

        # pulse timing
        self.pulse_in_progress = False
        self.pulse_start_ms = 0

        # hold (tipped) timing
        self.away_start_ms = 0
        self.tipped_fired = False
        self.suppress_pulses = False  # once tipped fires, ignore pulses until return-to-rest

        # sequence aggregation
        self.seq_count = 0
        self.seq_short = 0
        self.seq_long = 0
        self.last_pulse_end_ms = 0
        
    # ------------------------------------------------------------
    # setup / services
    # ------------------------------------------------------------

    def setup(self, settings):
        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        self.src_gpio = self.settings.get("src_gpio", "tilt_switch")

        self.rest_calibrate_ms = int(self.settings.get("rest_calibrate_ms", 2000))
        self.hold_ms = int(self.settings.get("hold_ms", 700))
        self.pulse_min_ms = int(self.settings.get("pulse_min_ms", 150))
        self.pulse_max_ms = int(self.settings.get("pulse_max_ms", 2500))
        self.long_ms = int(self.settings.get("long_ms", 1000))
        self.max_intertap_ms = int(self.settings.get("max_intertap_ms", 700))
        self.end_gap_ms = int(self.settings.get("end_gap_ms", 800))

        now = time.ticks_ms()
        self.last_transition_ms = now

        # reset runtime
        self.state_known = False
        self.rest_latched = False
        self.pulse_in_progress = False
        self.away_start_ms = 0
        self.tipped_fired = False
        self.suppress_pulses = False
        self._reset_sequence()
        self._create_events()

        self.state = self.STATE_OK
        self.set_status(6251, "Tilt gesture manager ready")

    def setup_services(self):
        hi = self.clb.get_event(f"gpio.{self.src_gpio}_high")
        lo = self.clb.get_event(f"gpio.{self.src_gpio}_low")

        if hi:
            hi.subscribe(self.on_gpio_high)
            print(f"[TILT_G] Subscribed: gpio.{self.src_gpio}_high")
        else:
            print(f"[TILT_G] Missing: gpio.{self.src_gpio}_high")

        if lo:
            lo.subscribe(self.on_gpio_low)
            print(f"[TILT_G] Subscribed: gpio.{self.src_gpio}_low")
        else:
            print(f"[TILT_G] Missing: gpio.{self.src_gpio}_low")

    # ------------------------------------------------------------
    # event-driven transitions
    # ------------------------------------------------------------

    def on_gpio_high(self, event, data):
        self._on_transition(1)

    def on_gpio_low(self, event, data):
        self._on_transition(0)

    def _on_transition(self, new_state: int):
        now = time.ticks_ms()

        self.current_state = 1 if new_state else 0
        self.state_known = True
        self.last_transition_ms = now

        # If we haven't latched rest yet, we just keep resetting the quiet timer.
        if not self.rest_latched:
            return
    
        # Pulse logic: start when leaving rest; end when returning to rest
        if (not self.pulse_in_progress) and (self.current_state != self.rest_state):
            self.pulse_in_progress = True
            self.pulse_start_ms = now

            # start hold timing too (away-from-rest began)
            self.away_start_ms = now
            self.tipped_fired = False
            return

        if self.pulse_in_progress and (self.current_state == self.rest_state):
            width = time.ticks_diff(now, self.pulse_start_ms)
            self.pulse_in_progress = False
            self.away_start_ms = 0
            self.tipped_fired = False

            if self.pulse_min_ms <= width <= self.pulse_max_ms:
                self._on_pulse_complete(width, now)
            return

        # If we bounced between non-rest states (rare with debounced events),
        # restart timing to remain predictable:
        if self.pulse_in_progress and (self.current_state != self.rest_state):
            self.pulse_start_ms = now
            self.away_start_ms = now
            self.tipped_fired = False

    # ------------------------------------------------------------
    # timers (need update() because they depend on *silence*)
    # ------------------------------------------------------------

    def update(self):
        if not self.state_known:
            return

        now = time.ticks_ms()

        # Rest calibration: latch rest after quiet period
        if not self.rest_latched:
            quiet_for = time.ticks_diff(now, self.last_transition_ms)
            if quiet_for >= self.rest_calibrate_ms:
                self.rest_state = self.current_state
                self.rest_latched = True
                self.pulse_in_progress = False
                self.away_start_ms = 0
                self.tipped_fired = False
                self.suppress_pulses = False
                self._reset_sequence()
                print(f"[TILT_G] rest_state latched={self.rest_state}")
            return

        # Hold/tipped: away from rest continuously for hold_ms
        if (not self.suppress_pulses) and (self.current_state != self.rest_state) and self.away_start_ms:
            if (not self.tipped_fired) and (time.ticks_diff(now, self.away_start_ms) >= self.hold_ms):
                self.tipped_fired = True
                self._publish("tipped", {"t_ms": now, "held_ms": time.ticks_diff(now, self.away_start_ms)})

        # Pulse timeout safety (if it never returns)
        if self.pulse_in_progress:
            if time.ticks_diff(now, self.pulse_start_ms) > self.pulse_max_ms:
                self.pulse_in_progress = False

        # Sequence end: gap since last pulse end
        if self.seq_count > 0 and (not self.pulse_in_progress):
            gap = time.ticks_diff(now, self.last_pulse_end_ms)
            if gap >= self.end_gap_ms:
                self._publish_sequence(now)

    # ------------------------------------------------------------
    # pulse + sequence
    # ------------------------------------------------------------

    def _on_pulse_complete(self, width_ms, now):
        payload = {"t_ms": now, "width_ms": width_ms}
        self._publish("pulse", payload)

        is_long = width_ms >= self.long_ms
        if is_long:
            self._publish("long", payload)
        else:
            self._publish("short", payload)

        # group sequences based on time between pulse ENDS
        if self.seq_count > 0:
            dt = time.ticks_diff(now, self.last_pulse_end_ms)
            if dt > self.max_intertap_ms:
                self._publish_sequence(now)

        self.seq_count += 1
        if is_long:
            self.seq_long += 1
        else:
            self.seq_short += 1

        self.last_pulse_end_ms = now

    def _publish_sequence(self, now):
        payload = {"t_ms": now, "count": self.seq_count, "short": self.seq_short, "long": self.seq_long}
        self._publish("sequence", payload)
        self._reset_sequence()

    def _reset_sequence(self):
        self.seq_count = 0
        self.seq_short = 0
        self.seq_long = 0
        self.last_pulse_end_ms = 0

    # ------------------------------------------------------------
    # events
    # ------------------------------------------------------------

    def _create_events(self):
        for ev in ("tipped", "returned", "pulse", "short", "long", "sequence"):
            self.events[f"tilt.{ev}"] = Event(
                name=f"tilt.{ev}",
                description=f"Tilt gesture: {ev}",
                owner=self
            )

    def _publish(self, ev, payload):
        payload["src_gpio"] = self.src_gpio
        self.events[f"tilt.{ev}"].publish(payload)

    def get_published_events(self):
        return [
            {"name": f"tilt.tipped", "description": "Held tipped >= hold_ms"},
            {"name": f"tilt.returned", "description": "Returned to rest after tipped"},
            {"name": f"tilt.pulse", "description": "Tip-and-return pulse completed"},
            {"name": f"tilt.short", "description": "Short pulse (< long_ms)"},
            {"name": f"tilt.long", "description": "Long pulse (>= long_ms)"},
            {"name": f"tilt.sequence", "description": "Pulse sequence ended"},
        ]
