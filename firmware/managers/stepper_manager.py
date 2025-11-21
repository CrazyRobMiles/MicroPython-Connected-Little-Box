from managers.base import CLBManager
import machine, math, time, sys

# ======== LOW-JITTER, SINGLE-CORE, TIMER-DRIVEN STEPPER MANAGER ========

class Manager(CLBManager):
    """
    Drives 1–4 x 28BYJ-48 steppers via ULN2003 (4 pins each) using an 8-step half-step sequence.
    - Waveforms are generated inside a hardware Timer IRQ (single-core).
    - PythonIsh API: move(distance_mm, intime=None), rotate(angle_deg, intime=None), arc(radius_mm, angle_deg, intime=None).
    - Console commands mirror the methods for manual testing.
    - 'min_step_delay_us' is the minimum (fastest) step interval; slower is used when 'intime' is given.
    """

    version = "1.1.0"
    dependencies = []  # none

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

    def __init__(self,clb):
        super().__init__(clb,defaults={
            # Up to four motors; -1 pins mean “unused motor”
            "motors": [
                {"pins":[-1,-1,-1,-1], "wheel_diameter_mm":69.0},  # 0: left
                {"pins":[-1,-1,-1,-1], "wheel_diameter_mm":69.0},  # 1: right
                {"pins":[-1,-1,-1,-1], "wheel_diameter_mm":69.0},  # 2: optional
                {"pins":[-1,-1,-1,-1], "wheel_diameter_mm":69.0},  # 3: optional
            ],
            "wheel_spacing_mm": 110.0,   # centre-to-centre
            "steps_per_rev":    4096,    # half-step figure for 28BYJ-48
            "min_step_delay_us": 1200,   # MIN (fastest) delay between steps
            "enabled":          False
        })
        self._m = []          # runtime motor blocks
        self._timer = None
        self._tick_us = 200    # timer tick period; ISR checks due steps at this cadence
        self._moving_any = False

    # ---------- CLB lifecycle ----------

    def setup(self, settings):
        super().setup(settings)
        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        try:
            self._build_motors()
            self._start_timer()
            self.state = self.STATE_OK
            self.set_status(7100, f"Stepper ready ({len(self._m)} motor(s)), IRQ tick {self._tick_us}µs")
        except Exception as e:
            self.state = self.STATE_ERROR
            sys.print_exception(e)
            self.set_status(7101, f"Stepper init error: {e}")

    def teardown(self):
        try:
            if self._timer:
                self._timer.deinit()
                self._timer = None
        except Exception:
            pass
        # coils off
        for m in self._m:
            p1,p2,p3,p4 = m["pins"]
            p1.value(0); p2.value(0); p3.value(0); p4.value(0)
        self._m.clear()
        self._moving_any = False
        self.set_status(7112, "Stepper manager torn down")

    # ---------- Configuration / build ----------

    def _build_motors(self):
        self._m = []
        min_delay = int(self.settings["min_step_delay_us"])
        for idx, cfg in enumerate(self.settings.get("motors", [])[:4]):
            pins = cfg.get("pins", [])
            if len(pins) != 4 or any(p < 0 for p in pins):
                continue
            pin_objs = [machine.Pin(p, machine.Pin.OUT) for p in pins]
            for p in pin_objs: p.value(0)
            self._m.append({
                "index": idx,
                "pins":  pin_objs,
                "seq":   0,                # 0..7
                "dir":   1,                # +1/-1
                "remain": 0,               # remaining steps (unsigned counter used in ISR)
                "delay":  min_delay,       # µs between steps for this motor
                "next":   time.ticks_us(), # next due time
                "wheel_diam": float(cfg.get("wheel_diameter_mm", 69.0)),
            })

    def _start_timer(self):
        # Use a high-rate periodic timer; ISR handles multi-motor scheduling.
        # On RP2040 MicroPython, Timer supports freq or period(ms).
        self._timer = machine.Timer()
        # Aim for ~200 µs tick so we can honour 1200 µs min reliably.
        self._timer.init(freq=int(1_000_000 // self._tick_us), mode=machine.Timer.PERIODIC, callback=self._irq_stepper)

    # ---------- IRQ: precise stepping ----------

    # Keep ISR tiny: no allocation, no printing, no float math, no exceptions.
    def _irq_stepper(self, _t):
        now = time.ticks_us()
        moving = False
        seq_len = 8
        half = self.HALFSTEP
        for m in self._m:
            if m["remain"] == 0:
                continue
            # If due, emit one step
            if time.ticks_diff(now, m["next"]) >= 0:
                m["seq"] = (m["seq"] + (1 if m["dir"] > 0 else -1)) % seq_len
                a,b,c,d = half[m["seq"]]
                p1,p2,p3,p4 = m["pins"]
                # Set coils
                p1.value(a); p2.value(b); p3.value(c); p4.value(d)
                # Countdown
                m["remain"] -= 1
                # Next due
                m["next"] = time.ticks_add(now, m["delay"])
            moving = moving or (m["remain"] != 0)
        # Cheap “@moving” flag for status/poll
        self._moving_any = moving

    # ---------- Kinematics / planning (non-IRQ) ----------

    def _motor(self, i):
        for m in self._m:
            if m["index"] == i:
                return m
        return None

    def _circ(self, m):
        return math.pi * m["wheel_diam"]

    def _mm_to_steps(self, m, mm):
        revs = mm / self._circ(m)
        return int(round(revs * int(self.settings["steps_per_rev"])))

    def _apply_time_pair(self, left_mm, right_mm, seconds=None):
        """Compute per-step interval; enforce min_step_delay_us. Accepts seconds instead of ticks."""
        if seconds is None:
            interval = int(self.settings["min_step_delay_us"])
        else:
            steps = 0
            L = self._motor(0)
            R = self._motor(1)
            if L: steps = max(steps, abs(self._mm_to_steps(L, left_mm)))
            if R: steps = max(steps, abs(self._mm_to_steps(R, right_mm)))
            if steps <= 1 or seconds <= 0:
                interval = int(self.settings["min_step_delay_us"])
            else:
                requested = int((seconds * 1_000_000) / steps)
                interval = max(requested, int(self.settings["min_step_delay_us"]))

        irq_state = machine.disable_irq()
        try:
            for m in self._m:
                m["delay"] = interval
        finally:
            machine.enable_irq(irq_state)
        self._last_interval_us = interval

    def _queue_motor_mm(self, idx, distance_mm):
        """Plan motion for one motor, setting remaining steps, direction, and next-due time safely."""
        m = self._motor(idx)
        if not m:
            return
        steps_signed = self._mm_to_steps(m, distance_mm)
        irq_state = machine.disable_irq()     # avoid ISR race
        try:
            m["dir"] = 1 if steps_signed >= 0 else -1
            m["remain"] = abs(steps_signed)
            m["next"] = time.ticks_us()       # start immediately
        finally:
            machine.enable_irq(irq_state)

    # ---------- PythonIsh API ----------

    def move(self, distance_mm, seconds=None):
        self._queue_motor_mm(0, distance_mm)
        self._queue_motor_mm(1, distance_mm)
        self._apply_time_pair(distance_mm, distance_mm, seconds)
        self.state = self.STATE_MOVING
        self.set_status(7200, f"move({distance_mm}, {seconds}s) interval={self._last_interval_us}µs")

    def rotate(self, angle_deg, seconds=None):
        spacing = float(self.settings["wheel_spacing_mm"])
        arc_len = (math.pi * spacing * angle_deg) / 360.0
        self._queue_motor_mm(0, +arc_len)
        self._queue_motor_mm(1, -arc_len)
        self._apply_time_pair(+arc_len, -arc_len, seconds)
        self.state = self.STATE_MOVING
        self.set_status(7201, f"rotate({angle_deg}, {seconds}s) interval={self._last_interval_us}µs")

    def arc(self, radius_mm, angle_deg, seconds=None):
        spacing = float(self.settings["wheel_spacing_mm"])
        rL = radius_mm - spacing/2.0
        rR = radius_mm + spacing/2.0
        dL = (2.0 * math.pi * rL) * (angle_deg / 360.0)
        dR = (2.0 * math.pi * rR) * (angle_deg / 360.0)
        self._queue_motor_mm(0, dL)
        self._queue_motor_mm(1, dR)
        self._apply_time_pair(dL, dR, seconds)
        self.state = self.STATE_MOVING
        self.set_status(7202, f"arc({radius_mm}, {angle_deg}, {seconds}s) interval={self._last_interval_us}µs")

    def get_interface(self):
        return {
            "move":   ("move <mm> [seconds]", self._cmd_move),
            "rotate": ("rotate <deg> [seconds]", self._cmd_rotate),
            "arc":    ("arc <radius_mm> <angle_deg> [seconds]", self._cmd_arc),
            "stop":   ("Immediate stop (motors off)", self._cmd_stop),
            "moving": ("Report whether motors are moving", self._cmd_moving)
        }

    def _cmd_move(self, *args):
        if not args: raise ValueError("move <mm> [seconds]")
        dist = float(args[0])
        secs = float(args[1]) if len(args) > 1 else None
        self.move(dist, secs)

    def _cmd_rotate(self, *args):
        if not args: raise ValueError("rotate <deg> [seconds]")
        ang = float(args[0])
        secs = float(args[1]) if len(args) > 1 else None
        self.rotate(ang, secs)

    def _cmd_arc(self, *args):
        if len(args) < 2: raise ValueError("arc <radius_mm> <angle_deg> [seconds]")
        radius = float(args[0])
        angle  = float(args[1])
        secs   = float(args[2]) if len(args) > 2 else None
        self.arc(radius, angle, secs)

    def _cmd_stop(self, *args):
        # zero remaining and drop coils
        for m in self._m:
            m["remain"] = 0
            p1,p2,p3,p4 = m["pins"]
            p1.value(0); p2.value(0); p3.value(0); p4.value(0)
        self.state = self.STATE_OK
        self.set_status(7203, "Stopped")

    def _cmd_moving(self, *args):
        return self._moving_any

    # ---------- CLB update() ----------

    def update(self):
        # Nothing time-critical here; just state maintenance
        if self.state == self.STATE_MOVING and not self._moving_any:
            # finished; release coils to save current
            for m in self._m:
                p1,p2,p3,p4 = m["pins"]
                p1.value(0); p2.value(0); p3.value(0); p4.value(0)
            self.state = self.STATE_OK
            self.set_status(7205, "Move complete")
