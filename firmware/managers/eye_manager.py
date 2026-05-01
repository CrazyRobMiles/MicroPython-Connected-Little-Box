from managers.base_manager import CLBDeviceManager
from managers.event import Event
import random
import time


class Manager(CLBDeviceManager):
    version = "0.2.0"
    dependencies = ["pca9685"]

    REQUIRED_SERVO_NAMES = (
        "eyes.lr",
        "eyes.ud",
        "left.upperlid",
        "left.lowerlid",
        "right.upperlid",
        "right.lowerlid",
    )

    device_default_settings = {
        "centre_x": 0.5,
        "centre_y": 0.5,
        "normal_open": 0.5,
        "blink_closed_open": 0.0,
        "blink_close_ms": 70,
        "blink_hold_ms": 25,
        "blink_open_ms": 90,
        "default_move_ms": 100,
        "orchestrations": {},
        "idle_animation": False,
        "idle_min_gap_ms": 1500,
        "idle_max_gap_ms": 5000,
        "idle_blink_chance": 0.35,
        "idle_saccade_min_ms": 50,
        "idle_saccade_max_ms": 140,
        "idle_return_chance": 0.35,
        "idle_max_offset_x": 0.35,
        "idle_max_offset_y": 0.25,
        "idle_open_jitter": 0.0,
    }

    def __init__(self, clb):
        super().__init__(clb)
        self.servo = None
        self.pose = {
            "x": 0.5,
            "y": 0.5,
            "open": 0.5,
        }
        self._active_run = None
        self._idle_running = False
        self._idle_next_ms = 0
        self._idle_last_target = None
        self.events = {
            "eye.pose_changed": Event(
                "eye.pose_changed",
                "Published when the stored eye pose changes.",
                self,
            ),
            "eye.animation_started": Event(
                "eye.animation_started",
                "Published when an eye animation/orchestration starts.",
                self,
            ),
            "eye.animation_completed": Event(
                "eye.animation_completed",
                "Published when an eye animation/orchestration completes.",
                self,
            ),
            "eye.animation_cancelled": Event(
                "eye.animation_cancelled",
                "Published when an eye animation/orchestration is cancelled.",
                self,
            ),
            "eye.animation_error": Event(
                "eye.animation_error",
                "Published when an eye animation/orchestration fails.",
                self,
            ),
            "eye.blink_completed": Event(
                "eye.blink_completed",
                "Published when a blink animation completes.",
                self,
            ),
            "eye.idle_started": Event(
                "eye.idle_started",
                "Published when idle animation is enabled.",
                self,
            ),
            "eye.idle_stopped": Event(
                "eye.idle_stopped",
                "Published when idle animation is disabled.",
                self,
            ),
            "eye.idle_step": Event(
                "eye.idle_step",
                "Published when the idle loop launches a new movement.",
                self,
            ),
        }

    def setup(self, settings):
        super().setup(settings)
        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        try:
            self.pose["x"] = self._clamp01(self.settings["centre_x"])
            self.pose["y"] = self._clamp01(self.settings["centre_y"])
            self.pose["open"] = self._clamp01(self.settings["normal_open"])
            self._idle_running = bool(self.settings.get("idle_animation", False))
            self._schedule_next_idle(initial=True)
            self.state = self.STATE_OK
            self.set_status(9200, "Eye manager ready")
        except Exception as e:
            self.state = self.STATE_ERROR
            self.set_status(9201, "Eye setup error: {}".format(e))

    def setup_services(self):
        if not self.enabled or self.state != self.STATE_OK:
            return

        self.servo = self.get_service_handle("pca9685")
        if not self.servo:
            self.state = self.STATE_ERROR
            self.set_status(9202, "Servo service unavailable")
            return

        try:
            for name in self.REQUIRED_SERVO_NAMES:
                self.servo.info(name)
        except Exception as e:
            self.state = self.STATE_ERROR
            self.set_status(9203, "Missing eye servo mapping: {}".format(e))
            return

        evt = self.clb.get_event("pca9685.orchestration_completed")
        if evt:
            evt.subscribe(self._on_servo_orchestration_completed)
        evt = self.clb.get_event("pca9685.orchestration_cancelled")
        if evt:
            evt.subscribe(self._on_servo_orchestration_cancelled)
        evt = self.clb.get_event("pca9685.orchestration_error")
        if evt:
            evt.subscribe(self._on_servo_orchestration_error)

        self.set_status(9204, "Eye manager connected to servo service")

        if self._idle_running:
            self.events["eye.idle_started"].publish({
                "startup": True,
                "next_ms": self._idle_next_ms,
            })

    def get_interface(self):
        return {
            "centre": ("Centre the eye: centre(duration_ms)", self.command_centre),
            "look": ("Move eye to position: look(x, y, duration_ms)", self.command_look),
            "open": ("Set eyelid openness: open(amount, duration_ms)", self.command_open),
            "pose": ("Set full eye pose: pose(x, y, open, duration_ms)", self.command_pose),
            "blink": ("Blink the eye", self.command_blink),
            "run": ("Run named animation: run(name)", self.command_run_named),
            "stop": ("stop current eye animation", self.command_stop),
            "status": ("show eye pose", self.command_status),
            "start_idle": ("start idle animation", self.command_start_idle),
            "stop_idle": ("stop idle animation", self.command_stop_idle),
        }

    def update(self):
        if not self.enabled or self.state != self.STATE_OK:
            return
        if not self._idle_running:
            return
        if self._active_run:
            return
        if time.ticks_diff(time.ticks_ms(), self._idle_next_ms) < 0:
            return
        try:
            self._run_idle_step()
        except Exception as e:
            self.set_status(9214, "Idle animation error: {}".format(e))
            self._schedule_next_idle()

    # ---- Semantic API ---------------------------------------------------------

    def centre(self, duration_ms=None):
        return self.set_pose(
            self.settings["centre_x"],
            self.settings["centre_y"],
            self.pose["open"],
            duration_ms=duration_ms,
            animation_name="eye.centre",
        )

    def _positions_for_look(self, x, y):
        return {
            "eyes.lr": self._clamp01(x),
            "eyes.ud": self._clamp01(y),
        }

    def _apply_positions(self, positions, duration_ms, animation_name):
        duration_ms = self._coerce_duration(duration_ms)

        if duration_ms <= 0:
            for name, pos in positions.items():
                self.servo.set_position_name(name, pos)
            return {
                "mode": "direct",
                "name": animation_name,
                "positions": dict(positions),
            }

        orch = {
            "name": animation_name,
            "owner": "eye",
            "steps": [
                {
                    "duration_ms": duration_ms,
                    "positions": positions,
                }
            ],
        }
        result = self.servo.run(orch)
        self._active_run = result
        self.events["eye.animation_started"].publish({
            "name": animation_name,
            "run_id": result.get("run_id"),
            "pose": dict(self.pose),
        })
        return result
    
    def look(self, x, y, duration_ms=None):
        self._require_ready()
        x = self._clamp01(x)
        y = self._clamp01(y)

        result = self._apply_positions(
            self._positions_for_look(x, y),
            duration_ms,
            "eye.look",
        )

        self.pose["x"] = x
        self.pose["y"] = y
        self.events["eye.pose_changed"].publish(dict(self.pose))
        return result

    def set_open(self, amount, duration_ms=None):
        self._require_ready()
        amount = self._clamp01(amount)

        result = self._apply_positions(
            self._positions_for_open(amount),
            duration_ms,
            "eye.open",
        )

        self.pose["open"] = amount
        self.events["eye.pose_changed"].publish(dict(self.pose))
        return result
    
    def set_pose(self, x, y, open_amount, duration_ms=None, animation_name="eye.pose"):
        self._require_ready()
        x = self._clamp01(x)
        y = self._clamp01(y)
        open_amount = self._clamp01(open_amount)
        duration_ms = self._coerce_duration(duration_ms)

        positions = self._positions_for_pose(x, y, open_amount)
        if duration_ms <= 0:
            for name, pos in positions.items():
                self.servo.set_position_name(name, pos)
            self._set_pose_state(x, y, open_amount)
            return {
                "mode": "direct",
                "name": animation_name,
                "pose": dict(self.pose),
            }

        orch = {
            "name": animation_name,
            "owner": "eye",
            "steps": [
                {
                    "duration_ms": duration_ms,
                    "positions": positions,
                }
            ],
        }
        result = self.servo.run(orch)
        self._active_run = result
        self._set_pose_state(x, y, open_amount)
        self.events["eye.animation_started"].publish({
            "name": animation_name,
            "run_id": result.get("run_id"),
            "pose": dict(self.pose),
        })
        return result

    def blink(self):
        self._require_ready()
        closed = self._clamp01(self.settings["blink_closed_open"])
        reopen = self.pose["open"]
        orch = {
            "name": "eye.blink",
            "owner": "eye",
            "steps": [
                {
                    "duration_ms": int(self.settings["blink_close_ms"]),
                    "positions": self._positions_for_open(closed),
                },
                {
                    "wait_ms": int(self.settings["blink_hold_ms"]),
                },
                {
                    "duration_ms": int(self.settings["blink_open_ms"]),
                    "positions": self._positions_for_open(reopen),
                },
            ],
        }
        result = self.servo.run(orch)
        self._active_run = result
        self.events["eye.animation_started"].publish({
            "name": "eye.blink",
            "run_id": result.get("run_id"),
            "pose": dict(self.pose),
        })
        return result

    def run_named(self, name):
        self._require_ready()
        data = self.settings.get("orchestrations", {}).get(name)
        if data is None:
            raise ValueError("unknown eye orchestration: {}".format(name))

        if isinstance(data, dict) and data.get("type") == "pose":
            return self.set_pose(
                data.get("x", self.pose["x"]),
                data.get("y", self.pose["y"]),
                data.get("open", self.pose["open"]),
                duration_ms=data.get("duration_ms", self.settings["default_move_ms"]),
                animation_name="eye." + name,
            )

        if isinstance(data, dict) and data.get("type") == "blink":
            old = {
                "blink_close_ms": self.settings["blink_close_ms"],
                "blink_hold_ms": self.settings["blink_hold_ms"],
                "blink_open_ms": self.settings["blink_open_ms"],
                "blink_closed_open": self.settings["blink_closed_open"],
            }
            try:
                for key in old:
                    if key in data:
                        self.settings[key] = data[key]
                return self.blink()
            finally:
                for key, value in old.items():
                    self.settings[key] = value

        if isinstance(data, list):
            orch = {
                "name": "eye." + name,
                "owner": "eye",
                "steps": data,
            }
        elif isinstance(data, dict) and "steps" in data:
            orch = {
                "name": data.get("name", "eye." + name),
                "owner": "eye",
                "steps": data["steps"],
            }
        else:
            raise ValueError("unsupported eye orchestration format")

        result = self.servo.run(orch)
        self._active_run = result
        self.events["eye.animation_started"].publish({
            "name": orch["name"],
            "run_id": result.get("run_id"),
            "pose": dict(self.pose),
        })
        return result

    def stop(self):
        self._require_ready()
        if self._active_run:
            rid = self._active_run.get("run_id")
            result = self.servo.stop(rid)
            self._active_run = None
            return result
        return self.servo.stop_name("eye")

    def start_idle(self):
        self._require_ready()
        self._idle_running = True
        self._schedule_next_idle(initial=True)
        self.set_status(9210, "Idle animation started")
        payload = {"startup": False, "next_ms": self._idle_next_ms}
        self.events["eye.idle_started"].publish(payload)
        return payload

    def stop_idle(self):
        self._require_ready()
        self._idle_running = False
        self._idle_next_ms = 0
        self.set_status(9211, "Idle animation stopped")
        payload = {"active_run": self._active_run}
        self.events["eye.idle_stopped"].publish(payload)
        return payload

    # ---- Internal helpers -----------------------------------------------------

    def _require_ready(self):
        if not self.enabled:
            raise RuntimeError("eye manager disabled")
        if self.state != self.STATE_OK:
            raise RuntimeError("eye manager not ready")
        if not self.servo:
            raise RuntimeError("servo service unavailable")

    def _clamp01(self, value):
        value = float(value)
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    def _coerce_duration(self, duration_ms):
        if duration_ms is None:
            return int(self.settings.get("default_move_ms", 0))
        return int(duration_ms)

    def _positions_for_open(self, open_amount):
        open_amount = self._clamp01(open_amount)
        return {
            "left.upperlid": open_amount,
            "left.lowerlid": open_amount,
            "right.upperlid": open_amount,
            "right.lowerlid": open_amount,
        }

    def _positions_for_pose(self, x, y, open_amount):
        positions = self._positions_for_open(open_amount)
        positions["eyes.lr"] = self._clamp01(x)
        positions["eyes.ud"] = self._clamp01(y)
        return positions

    def _set_pose_state(self, x, y, open_amount):
        self.pose["x"] = self._clamp01(x)
        self.pose["y"] = self._clamp01(y)
        self.pose["open"] = self._clamp01(open_amount)
        self.events["eye.pose_changed"].publish(dict(self.pose))

    def _schedule_next_idle(self, initial=False):
        if not self._idle_running:
            self._idle_next_ms = 0
            return
        now = time.ticks_ms()
        if initial:
            delay = 250
        else:
            low = int(self.settings.get("idle_min_gap_ms", 1500))
            high = int(self.settings.get("idle_max_gap_ms", 5000))
            if high < low:
                high = low
            delay = random.randint(low, high)
        self._idle_next_ms = time.ticks_add(now, delay)

    def _run_idle_step(self):
        blink_chance = float(self.settings.get("idle_blink_chance", 0.35))
        if random.random() < blink_chance:
            result = self.blink()
            self.events["eye.idle_step"].publish({
                "kind": "blink",
                "run_id": result.get("run_id"),
            })
            return result

        cx = self._clamp01(self.settings.get("centre_x", 0.5))
        cy = self._clamp01(self.settings.get("centre_y", 0.5))
        max_x = abs(float(self.settings.get("idle_max_offset_x", 0.35)))
        max_y = abs(float(self.settings.get("idle_max_offset_y", 0.25)))

        if self._idle_last_target and random.random() < float(self.settings.get("idle_return_chance", 0.35)):
            tx = cx
            ty = cy
            self._idle_last_target = None
            kind = "return"
        else:
            tx = self._clamp01(cx + random.uniform(-max_x, max_x))
            ty = self._clamp01(cy + random.uniform(-max_y, max_y))
            self._idle_last_target = {"x": tx, "y": ty}
            kind = "saccade"

        base_open = self.pose["open"]
        jitter = abs(float(self.settings.get("idle_open_jitter", 0.0)))
        if jitter > 0.0:
            base_open = self._clamp01(base_open + random.uniform(-jitter, jitter))

        low = int(self.settings.get("idle_saccade_min_ms", 50))
        high = int(self.settings.get("idle_saccade_max_ms", 140))
        if high < low:
            high = low
        dur = random.randint(low, high)

        result = self.set_pose(tx, ty, base_open, dur, animation_name="eye.idle")
        self.events["eye.idle_step"].publish({
            "kind": kind,
            "x": tx,
            "y": ty,
            "open": base_open,
            "duration_ms": dur,
            "run_id": result.get("run_id"),
        })
        return result

    def _on_servo_orchestration_completed(self, event, payload):
        if not payload:
            return
        if payload.get("owner") != "eye":
            return
        if self._active_run and payload.get("run_id") == self._active_run.get("run_id"):
            self._active_run = None
        self.events["eye.animation_completed"].publish(dict(payload))
        if payload.get("name") == "eye.blink":
            self.events["eye.blink_completed"].publish(dict(payload))
        if self._idle_running:
            self._schedule_next_idle()

    def _on_servo_orchestration_cancelled(self, event, payload):
        if not payload:
            return
        if payload.get("owner") != "eye":
            return
        if self._active_run and payload.get("run_id") == self._active_run.get("run_id"):
            self._active_run = None
        self.events["eye.animation_cancelled"].publish(dict(payload))
        if self._idle_running:
            self._schedule_next_idle()

    def _on_servo_orchestration_error(self, event, payload):
        if not payload:
            return
        if payload.get("owner") != "eye":
            return
        if self._active_run and payload.get("run_id") == self._active_run.get("run_id"):
            self._active_run = None
        self.events["eye.animation_error"].publish(dict(payload))
        if self._idle_running:
            self._schedule_next_idle()

    # ---- Settings hook --------------------------------------------------------

    def on_setting_changed(self, path, old_value, new_value):
        if path == "idle_animation":
            if bool(new_value):
                if self.enabled and self.state == self.STATE_OK and self.servo:
                    self.start_idle()
                else:
                    self._idle_running = True
                    self._schedule_next_idle(initial=True)
            else:
                if self.enabled and self.state == self.STATE_OK and self.servo:
                    self.stop_idle()
                else:
                    self._idle_running = False
                    self._idle_next_ms = 0
            return

        if path in ("centre_x", "centre_y", "normal_open"):
            try:
                self.pose["x"] = self._clamp01(self.settings.get("centre_x", self.pose["x"]))
                self.pose["y"] = self._clamp01(self.settings.get("centre_y", self.pose["y"]))
                if path == "normal_open":
                    self.pose["open"] = self._clamp01(self.settings.get("normal_open", self.pose["open"]))
            except Exception:
                pass

    # ---- Commands -------------------------------------------------------------

    def command_centre(self, duration_ms=None):
        return self.centre(duration_ms)

    def command_look(self, x, y, duration_ms=None):
        return self.look(x, y, duration_ms)

    def command_open(self, amount, duration_ms=None):
        return self.set_open(amount, duration_ms)

    def command_pose(self, x, y, open_amount, duration_ms=None):
        return self.set_pose(x, y, open_amount, duration_ms)

    def command_blink(self):
        return self.blink()

    def command_run_named(self, name):
        return self.run_named(name)

    def command_stop(self):
        return self.stop()

    def command_start_idle(self):
        return self.start_idle()

    def command_stop_idle(self):
        return self.stop_idle()

    def command_status(self):
        info = {
            "pose": dict(self.pose),
            "active_run": self._active_run,
            "idle_running": self._idle_running,
            "idle_next_ms": self._idle_next_ms,
        }
        print(info)
        return info
