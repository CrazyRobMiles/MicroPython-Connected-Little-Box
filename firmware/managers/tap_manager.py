# managers/tap_manager.py
from managers.base_manager import CLBManager
from managers.event import Event
import machine
import time


class Manager(CLBManager):
    version = "1.0.1"

    def __init__(self, clb):
        super().__init__(clb, defaults={
            "tap_pin": None,            # single GPIO number
            "name": "button",           # event namespace: tap.<name>.*
            "pullup": True,
            "active_level": 0,          # for pullup buttons, press reads LOW => 0
            "debounce_ms": 20,
            "max_intertap_ms": 500,
            "end_gap_ms": 500,
            "idle_ms": 1000,
        })

        self.s = None                 # single input state dict
        self.events = {}
        self.event_manager = None

    def setup(self, settings):
        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        pin_number = self.settings.get("tap_pin", None)
        if pin_number is None:
            self.set_status(6100, "Tap manager: tap_pin not set")
            self.state = self.STATE_ERROR
            return

        name = self.settings.get("name", "button")
        pullup = bool(self.settings.get("pullup", True))
        active_level = int(self.settings.get("active_level", 0 if pullup else 1))

        debounce_ms = int(self.settings.get("debounce_ms", 20))
        max_intertap_ms = int(self.settings.get("max_intertap_ms", 500))
        end_gap_ms = int(self.settings.get("end_gap_ms", 500))
        idle_ms = int(self.settings.get("idle_ms", 1000))

        self._create_events(name)

        try:
            if pullup:
                pin = machine.Pin(pin_number, machine.Pin.IN, machine.Pin.PULL_UP)
            else:
                pin = machine.Pin(pin_number, machine.Pin.IN)

            now = time.ticks_ms()
            raw = pin.value()

            self.s = {
                "name": name,
                "pin": pin,
                "pin_number": pin_number,

                # debouncing / edge detect
                "debounce_ms": debounce_ms,
                "active_level": active_level,
                "stable_state": raw,
                "last_raw": raw,
                "last_edge_ms": now,
                "last_activity_ms": now,

                # tap sequencing
                "tap_count": 0,
                "last_tap_ms": 0,
                "max_intertap_ms": max_intertap_ms,
                "end_gap_ms": end_gap_ms,

                # idle detection
                "idle_ms": idle_ms,
                "idle_fired": False,
            }

            self.state = self.STATE_OK
            self.set_status(6101, "Tap manager ready")
            print(f"[TAP] Configured GPIO {pin_number} as '{name}' (pullup={pullup}, active_level={active_level})")
        except Exception as e:
            self.set_status(6103, f"Tap manager setup failed: {e}")
            self.state = self.STATE_ERROR

    def setup_services(self):
        self.event_manager = self.get_service_handle("event")

    def update(self):
        if not self.s:
            return

        now = time.ticks_ms()
        pin = self.s["pin"]
        raw = pin.value()

        # Raw edge tracking
        if raw != self.s["last_raw"]:
            self.s["last_raw"] = raw
            self.s["last_edge_ms"] = now
            self.s["last_activity_ms"] = now
            self.s["idle_fired"] = False
        else:
            # Debounced stable-state update
            if raw != self.s["stable_state"]:
                if time.ticks_diff(now, self.s["last_edge_ms"]) >= self.s["debounce_ms"]:
                    prev = self.s["stable_state"]
                    self.s["stable_state"] = raw
                    self.s["last_activity_ms"] = now
                    self.s["idle_fired"] = False

                    # Press edge into active_level => tap
                    if prev != self.s["active_level"] and raw == self.s["active_level"]:
                        self._on_tap(now)

        # End-of-sequence detection
        if self.s["tap_count"] > 0:
            gap = time.ticks_diff(now, self.s["last_tap_ms"])
            if gap >= self.s["end_gap_ms"]:
                self._end_sequence(now)

        # Idle detection
        idle_for = time.ticks_diff(now, self.s["last_activity_ms"])
        if (not self.s["idle_fired"]) and idle_for >= self.s["idle_ms"]:
            self.s["idle_fired"] = True
            name = self.s["name"]
            self.events[f"tap.{name}.idle"].publish({
                "name": name,
                "idle_ms": self.s["idle_ms"],
                "idle_for_ms": idle_for
            })

    def _create_events(self, name: str):
        for ev in ("tap", "sequence", "double", "triple", "idle"):
            event_name = f"tap.{name}.{ev}"
            self.events[event_name] = Event(
                name=event_name,
                description=f"Tap event ({ev}) for '{name}'",
                owner=self
            )

    def _on_tap(self, now):
        # If too long since last tap, force-end any prior sequence
        if self.s["tap_count"] > 0:
            dt = time.ticks_diff(now, self.s["last_tap_ms"])
            if dt > self.s["max_intertap_ms"]:
                self._end_sequence(now)

        self.s["tap_count"] += 1
        self.s["last_tap_ms"] = now

        name = self.s["name"]
        self.events[f"tap.{name}.tap"].publish({
            "name": name,
            "count_so_far": self.s["tap_count"],
            "pin": self.s["pin_number"],
            "t_ms": now
        })

    def _end_sequence(self, now):
        count = self.s["tap_count"]
        if count <= 0:
            return

        self.s["tap_count"] = 0
        name = self.s["name"]

        payload = {"name": name, "count": count, "pin": self.s["pin_number"], "t_ms": now}
        self.events[f"tap.{name}.sequence"].publish(payload)

        if count == 2:
            self.events[f"tap.{name}.double"].publish(payload)
        elif count == 3:
            self.events[f"tap.{name}.triple"].publish(payload)

    def get_published_events(self):
        if not self.s:
            return []
        n = self.s["name"]
        return [
            {"name": f"tap.{n}.tap", "description": "Tap detected (per-tap)"},
            {"name": f"tap.{n}.sequence", "description": "Tap sequence ended (final count)"},
            {"name": f"tap.{n}.double", "description": "Double-tap convenience event"},
            {"name": f"tap.{n}.triple", "description": "Triple-tap convenience event"},
            {"name": f"tap.{n}.idle", "description": "No activity for idle_ms"},
        ]

    def teardown(self):
        if self.s:
            try:
                self.s["pin"].close()
            except:
                pass
        self.s = None
        self.set_status(6102, "Tap manager torn down")
