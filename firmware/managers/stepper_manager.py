from managers.base import CLBManager
import machine, math, time, sys

# NEW: cross-platform hardware abstraction layer
import compat
from compat import (
    start_periodic_timer,
    cancel_timer,
    monotonic_us,
)

# ======== CROSS-PLATFORM, TIMER-DRIVEN STEPPER MANAGER ========

class Manager(CLBManager):
    """
    Drives 1–4 x 28BYJ-48 steppers via ULN2003 (4 pins each) using an 8-step half-step sequence.
    - Uses compat.py to support both Pico (rp2) and ESP32 reliably.
    - High-resolution timers on Pico, safe ms timers on ESP32.
    - Public API: move(mm), rotate(deg), arc(radius, deg) + console commands.
    """

    version = "1.3.1"
    dependencies = []  # no automatic dependencies

    STATE_DISABLED = "disabled"
    STATE_READY    = "ready"
    STATE_ERROR    = "error"
    STATE_MOVING   = "moving"

    # 8-step half-step sequence (IN1..IN4)
    HALFSTEP = (
        (1,0,0,0),
        (1,1,0,0),
        (0,1,0,0),
        (0,1,1,0),
        (0,0,1,0),
        (0,0,1,1),
        (0,0,0,1),
        (1,0,0,1),
    )

    def __init__(self, clb):
        super().__init__(clb, defaults={
            # Up to four motors; -1 pins mean “unused motor”
            "motors": [
                {"pins":[-1,-1,-1,-1], "wheel_diameter_mm":69.0},  # motor 0: left
                {"pins":[-1,-1,-1,-1], "wheel_diameter_mm":69.0},  # motor 1: right
                {"pins":[-1,-1,-1,-1], "wheel_diameter_mm":69.0},  # optional
                {"pins":[-1,-1,-1,-1], "wheel_diameter_mm":69.0},  # optional
            ],
            "wheel_spacing_mm": 110.0,      # centre-to-centre distance
            "steps_per_rev":    4096,       # half-step count for 28BYJ-48
            "min_step_delay_us": 1200,      # fastest step interval
            "enabled":          False
        })
        self._m = []          # runtime motor data
        self._timer = None
        self._tick_us = 200    # target tick (compat adjusts on ESP32)
        self._moving_any = False
        self._last_interval_us = int(self.defaults["min_step_delay_us"])

    # ---------- Lifecycle ----------

    def setup(self, settings):
        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        try:
            self._build_motors()
            self._start_timer()

            self.state = self.STATE_READY
            self.set_status(7100,
                f"Stepper ready ({len(self._m)} motor(s)) on {compat.platform_name()}"
            )

        except Exception as e:
            self.state = self.STATE_ERROR
            sys.print_exception(e)
            self.set_status(7101, f"Stepper init error: {e}")

    def teardown(self):
        cancel_timer(self._timer)
        self._timer = None

        # Disable coils
        for m in self._m:
            p1,p2,p3,p4 = m["pins"]
            p1.value(0); p2.value(0); p3.value(0); p4.value(0)

        self._m.clear()
        self._moving_any = False
        self.set_status(7112, "Stepper manager torn down")

    # ---------- Internal motor setup ----------

    def _build_motors(self):
        self._m = []
        min_delay = int(self.settings["min_step_delay_us"])

        for idx, cfg in enumerate(self.settings.get("motors", [])[:4]):
            pins = cfg.get("pins", [])

            # Skip inactive motors
            if len(pins) != 4 or any(p < 0 for p in pins):
                continue

            # ESP32-safe pin creation
            pin_objs = [machine.Pin(p, machine.Pin.OUT) for p in pins]
            for p in pin_objs:
                p.value(0)

            self._m.append({
                "index": idx,
                "pins": pin_objs,
                "seq": 0,
                "dir": 1,
                "remain": 0,
                "delay": min_delay,
                "next": monotonic_us(),
                "wheel_diam": float(cfg.get("wheel_diameter_mm", 69.0)),
            })

    def _start_timer(self):
        # compat.start_periodic_timer chooses the correct timer mode per board
        self._timer = start_periodic_timer(self._irq_stepper, self._tick_us)

    # ---------- Timer callback (ISR-safe) ----------

    def _irq_stepper(self):
        now = monotonic_us()
        moving = False
        seq_len = 8
        half = self.HALFSTEP

        for m in self._m:
            if m["remain"] == 0:
                continue

            if time.ticks_diff(now, m["next"]) >= 0:
                # Update sequence
                m["seq"] = (m["seq"] + (1 if m["dir"] > 0 else -1)) % seq_len
                a,b,c,d = half[m["seq"]]
                p1,p2,p3,p4 = m["pins"]

                # Coil drive
                p1.value(a); p2.value(b); p3.value(c); p4.value(d)

                # Count down
                m["remain"] -= 1
                m["next"] = time.ticks_add(now, m["delay"])

            moving = moving or (m["remain"] != 0)

        self._moving_any = moving

    # ---------- Motion planning ----------

    def _motor(self, idx):
        for m in self._m:
            if m["index"] == idx:
                return m
        return None

    def _circ(self, m): return math.pi * m["wheel_diam"]

    def _mm_to_steps(self, m, mm):
        revs = mm / self._circ(m)
        return int(round(revs * int(self.settings["steps_per_rev"])))

    def _apply_time_pair(self, left_mm, right_mm, seconds=None):
        """Compute step interval based on motion time or use min_step_delay."""
        if seconds is None:
            interval = int(self.settings["min_step_delay_us"])
        else:
            L = self._motor(0)
            R = self._motor(1)
            steps_L = abs(self._mm_to_steps(L, left_mm)) if L else 0
            steps_R = abs(self._mm_to_steps(R, right_mm)) if R else 0
            steps = max(steps_L, steps_R)

            if steps <= 1 or seconds <= 0:
                interval = int(self.settings["min_step_delay_us"])
            else:
                requested = int((seconds * 1_000_000) / steps)
                interval = max(requested, int(self.settings["min_step_delay_us"]))

        irq = machine.disable_irq()
        try:
            for m in self._m:
                m["delay"] = interval
        finally:
            machine.enable_irq(irq)

        self._last_interval_us = interval

    def _queue_motor_mm(self, idx, distance_mm):
        m = self._motor(idx)
        if not m:
            return

        steps_signed = self._mm_to_steps(m, distance_mm)
        irq = machine.disable_irq()
        try:
            m["dir"] = 1 if steps_signed >= 0 else -1
            m["remain"] = abs(steps_signed)
            m["next"] = monotonic_us()
        finally:
            machine.enable_irq(irq)

    # ---------- Public API ----------

    def move(self, distance_mm, seconds=None):
        self._queue_motor_mm(0, distance_mm)
        self._queue_motor_mm(1, distance_mm)
        self._apply_time_pair(distance_mm, distance_mm, seconds)

        self.state = self.STATE_MOVING
        self.set_status(
            7200, f"move({distance_mm}, {seconds}) interval={self._last_interval_us}us"
        )

    def rotate(self, angle_deg, seconds=None):
        spacing = float(self.settings["wheel_spacing_mm"])
        arc_len = (math.pi * spacing * angle_deg) / 360.0

        self._queue_motor_mm(0, +arc_len)
        self._queue_motor_mm(1, -arc_len)
        self._apply_time_pair(+arc_len, -arc_len, seconds)

        self.state = self.STATE_MOVING
        self.set_status(
            7201, f"rotate({angle_deg}, {seconds}) interval={self._last_interval_us}us"
        )

    def arc(self, radius_mm, angle_deg, seconds=None):
        spacing = float(self.settings["wheel_spacing_mm"])
        rL = radius_mm - spacing/2.0
        rR = radius_mm + spacing/2.0

        dL = (2 * math.pi * rL) * (angle_deg / 360.0)
        dR = (2 * math.pi * rR) * (angle_deg / 360.0)

        self._queue_motor_mm(0, dL)
        self._queue_motor_mm(1, dR)
        self._apply_time_pair(dL, dR, seconds)

        self.state = self.STATE_MOVING
        self.set_status(
            7202, f"arc({radius_mm}, {angle_deg}, {seconds}) interval={self._last_interval_us}us"
        )

    # ---------- Console API ----------

    def get_interface(self):
        return {
            "move":   ("move <mm> [seconds]", self._cmd_move),
            "rotate": ("rotate <deg> [seconds]", self._cmd_rotate),
            "arc":    ("arc <radius> <degrees> [seconds]", self._cmd_arc),
            "stop":   ("Stop motors immediately", self._cmd_stop),
            "moving": ("Return whether motors are moving", self._cmd_moving),
        }

    def _cmd_move(self, *args):
        if not args:
            raise ValueError("move <mm> [seconds]")
        dist = float(args[0])
        secs = float(args[1]) if len(args) > 1 else None
        self.move(dist, secs)

    def _cmd_rotate(self, *args):
        if not args:
            raise ValueError("rotate <deg> [seconds]")
        ang = float(args[0])
        secs = float(args[1]) if len(args) > 1 else None
        self.rotate(ang, secs)

    def _cmd_arc(self, *args):
        if len(args) < 2:
            raise ValueError("arc <radius_mm> <angle_deg> [seconds]")
        radius = float(args[0])
        angle  = float(args[1])
        secs   = float(args[2]) if len(args) > 2 else None
        self.arc(radius, angle, secs)

    def _cmd_stop(self, *args):
        for m in self._m:
            m["remain"] = 0
            p1,p2,p3,p4 = m["pins"]
            p1.value(0); p2.value(0); p3.value(0); p4.value(0)
        self.state = self.STATE_READY
        self.set_status(7203, "Stopped")

    def _cmd_moving(self, *args):
        self.set_status(7204, "moving" if self._moving_any else "stopped")

    # ---------- CLB update loop ----------

    def update(self):
        if self.state == self.STATE_MOVING and not self._moving_any:
            # End of movement
            for m in self._m:
                p1,p2,p3,p4 = m["pins"]
                p1.value(0); p2.value(0); p3.value(0); p4.value(0)

            self.state = self.STATE_READY
            self.set_status(7205, "Move complete")
