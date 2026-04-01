from managers.base_manager import CLBManager
from managers.event import Event
import sys
import time

try:
    import machine
except Exception:
    machine = None


class _PCA9685:
    MODE1 = 0x00
    PRESCALE = 0xFE
    LED0_ON_L = 0x06

    def __init__(self, i2c, address=0x40):
        self.i2c = i2c
        self.address = address
        self.freq_hz = 50
        self._write8(self.MODE1, 0x00)

    def _write8(self, register, value):
        self.i2c.writeto_mem(self.address, register, bytes((value & 0xFF,)))

    def _read8(self, register):
        return self.i2c.readfrom_mem(self.address, register, 1)[0]

    def set_pwm_freq(self, freq_hz):
        self.freq_hz = int(freq_hz)
        prescaleval = 25000000.0
        prescaleval /= 4096.0
        prescaleval /= float(self.freq_hz)
        prescaleval -= 1.0
        prescale = int(prescaleval + 0.5)

        oldmode = self._read8(self.MODE1)
        sleep = (oldmode & 0x7F) | 0x10
        self._write8(self.MODE1, sleep)
        self._write8(self.PRESCALE, prescale)
        self._write8(self.MODE1, oldmode)
        time.sleep_ms(5)
        self._write8(self.MODE1, oldmode | 0xA1)

    def set_pwm(self, channel, on_count, off_count):
        base = self.LED0_ON_L + 4 * int(channel)
        data = bytes((
            on_count & 0xFF,
            (on_count >> 8) & 0x0F,
            off_count & 0xFF,
            (off_count >> 8) & 0x0F,
        ))
        self.i2c.writeto_mem(self.address, base, data)

    def set_channel_off(self, channel):
        base = self.LED0_ON_L + 4 * int(channel)
        data = bytes((0x00, 0x00, 0x00, 0x10))
        self.i2c.writeto_mem(self.address, base, data)

    def set_pulse_us(self, channel, pulse_us):
        period_us = 1000000.0 / float(self.freq_hz)
        ticks = int((float(pulse_us) * 4096.0) / period_us)
        if ticks < 0:
            ticks = 0
        if ticks > 4095:
            ticks = 4095
        self.set_pwm(channel, 0, ticks)
        return ticks


class Manager(CLBManager):
    version = "1.2.0"
    dependencies = []

    def __init__(self, clb):
        super().__init__(clb, defaults=self._build_defaults())
        self.i2c = None
        self.driver = None
        self._runtime = {}
        self._servos_by_channel = {}
        self._servos_by_name = {}
        self._active_runs = []
        self._next_run_id = 1
        self.events = {
            "pca9685.servo_moved": Event(
                "pca9685.servo_moved",
                "Published when a servo is moved to a new logical position or degree value.",
                self,
            ),
            "pca9685.servo_reset": Event(
                "pca9685.servo_reset",
                "Published when a servo is reset to its configured reset position.",
                self,
            ),
            "pca9685.reset_all": Event(
                "pca9685.reset_all",
                "Published when all configured servos are reset.",
                self,
            ),
            "pca9685.calibration_changed": Event(
                "pca9685.calibration_changed",
                "Published when start/reset/stop calibration values are changed.",
                self,
            ),
            "pca9685.orchestration_started": Event(
                "pca9685.orchestration_started",
                "Published when an orchestration starts.",
                self,
            ),
            "pca9685.orchestration_step": Event(
                "pca9685.orchestration_step",
                "Published when an orchestration enters a new step.",
                self,
            ),
            "pca9685.orchestration_completed": Event(
                "pca9685.orchestration_completed",
                "Published when an orchestration completes.",
                self,
            ),
            "pca9685.orchestration_cancelled": Event(
                "pca9685.orchestration_cancelled",
                "Published when an orchestration is cancelled.",
                self,
            ),
            "pca9685.orchestration_error": Event(
                "pca9685.orchestration_error",
                "Published when an orchestration fails.",
                self,
            ),
        }

    def _build_defaults(self):
        return {
            "i2c_bus": 0,
            "i2c_sda_pin": 4,
            "i2c_scl_pin": 5,
            "address": 0x40,
            "pwm_frequency": 50,
            "pulse_min_us": 500,
            "pulse_max_us": 2500,
            "move_on_setup": True,
            "orchestrations": {},
            "servos": [],
        }

    def setup(self, settings):
        super().setup(settings)
        self._active_runs = []
        self._next_run_id = 1
        self._build_runtime_cache()

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        if machine is None:
            self.state = self.STATE_ERROR
            self.set_status(9101, "machine module unavailable")
            return

        try:
            self._validate_all_settings()

            sda = machine.Pin(self.settings["i2c_sda_pin"])
            scl = machine.Pin(self.settings["i2c_scl_pin"])
            self.i2c = machine.I2C(self.settings["i2c_bus"], sda=sda, scl=scl)

            devices = self.i2c.scan()
            addr = int(self.settings["address"])
            if addr not in devices:
                raise RuntimeError("PCA9685 not found on I2C bus at address 0x{:02X}".format(addr))

            self.driver = _PCA9685(self.i2c, addr)
            self.driver.set_pwm_freq(self.settings["pwm_frequency"])

            for channel, servo in self._servos_by_channel.items():
                pos = self._clamp_position(servo.get("position", 0.5))
                self._runtime[channel]["position"] = pos
                self._runtime[channel]["degrees"] = self._position_to_degrees(channel, pos)
                self._runtime[channel]["pulse_us"] = self._degrees_to_pulse_us(self._runtime[channel]["degrees"])

            self.state = self.STATE_OK
            self.set_status(9100, "PCA9685 ready")
        except Exception as e:
            self.driver = None
            self.i2c = None
            self.state = self.STATE_ERROR
            sys.print_exception(e)
            self.set_status(9102, "PCA9685 setup error: {}".format(e))

    def setup_services(self):
        if not self.enabled or self.state != self.STATE_OK:
            return

        if self.settings.get("move_on_setup", True):
            try:
                self.reset_all()
            except Exception as e:
                sys.print_exception(e)
                self.state = self.STATE_ERROR
                self.set_status(9103, "PCA9685 initial reset failed: {}".format(e))

    def update(self):
        if not self.enabled or self.state != self.STATE_OK:
            return

        now = time.ticks_ms()
        survivors = []
        for run in self._active_runs:
            try:
                if self._update_run(run, now):
                    survivors.append(run)
            except Exception as e:
                sys.print_exception(e)
                self.events["pca9685.orchestration_error"].publish({
                    "run_id": run.get("run_id"),
                    "name": run.get("name"),
                    "owner": run.get("owner"),
                    "error": str(e),
                })
        self._active_runs = survivors

    def get_interface(self):
        return {
            "set_position": ("set_position <channel> <0..1>", self.command_set_position),
            "set_position_name": ("set_position_name <name> <0..1>", self.command_set_position_name),
            "set_degrees": ("set_degrees <channel> <degrees>", self.command_set_degrees),
            "set_degrees_name": ("set_degrees_name <name> <degrees>", self.command_set_degrees_name),
            "reset": ("reset <channel>", self.command_reset),
            "reset_name": ("reset_name <name>", self.command_reset_name),
            "reset_all": ("reset_all", self.command_reset_all),
            "off": ("off <channel>", self.command_off),
            "off_name": ("off_name <name>", self.command_off_name),
            "off_all": ("off_all", self.command_off_all),
            "list": ("list all configured servos", self.command_list),
            "info": ("info <channel|name>", self.command_info),
            "capture_start": ("capture_start <channel>", self.command_capture_start),
            "capture_reset": ("capture_reset <channel>", self.command_capture_reset),
            "capture_stop": ("capture_stop <channel>", self.command_capture_stop),
            "capture_start_name": ("capture_start_name <name>", self.command_capture_start_name),
            "capture_reset_name": ("capture_reset_name <name>", self.command_capture_reset_name),
            "capture_stop_name": ("capture_stop_name <name>", self.command_capture_stop_name),
            "set_start": ("set_start <channel> <degrees>", self.command_set_start),
            "set_reset": ("set_reset <channel> <degrees>", self.command_set_reset),
            "set_stop": ("set_stop <channel> <degrees>", self.command_set_stop),
            "set_start_name": ("set_start_name <name> <degrees>", self.command_set_start_name),
            "set_reset_name": ("set_reset_name <name> <degrees>", self.command_set_reset_name),
            "set_stop_name": ("set_stop_name <name> <degrees>", self.command_set_stop_name),
            "run": ("run <orchestration_dict>", self.command_run),
            "run_named": ("run_named <name>", self.command_run_named),
            "stop": ("stop <run_id>", self.command_stop),
            "stop_name": ("stop_name <name>", self.command_stop_name),
            "stop_all": ("stop_all", self.command_stop_all),
            "running": ("running", self.command_running),
        }

    # --- Resolution / validation -------------------------------------------------

    def _build_runtime_cache(self):
        self._runtime = {}
        self._servos_by_channel = {}
        self._servos_by_name = {}
        for servo in self.settings.get("servos", []):
            channel = int(servo["channel"])
            name = str(servo["name"])
            pos = self._clamp_position(servo.get("position", 0.5))
            self._servos_by_channel[channel] = servo
            self._servos_by_name[name] = servo
            self._runtime[channel] = {
                "position": pos,
                "degrees": 0.0,
                "pulse_us": 0.0,
            }

    def _validate_servo(self, servo):
        required = ("channel", "name", "start", "reset", "stop")
        for field in required:
            if field not in servo:
                raise ValueError("servo definition missing '{}'".format(field))

        channel = int(servo["channel"])
        if channel < 0 or channel > 15:
            raise ValueError("servo channel out of range: {}".format(channel))

        name = str(servo["name"])
        if not name:
            raise ValueError("servo name must not be empty")

        start = float(servo["start"])
        reset = float(servo["reset"])
        stop = float(servo["stop"])

        if start == stop:
            raise ValueError("servo start and stop must not be equal")

        low = start if start < stop else stop
        high = stop if stop > start else start
        if reset < low or reset > high:
            raise ValueError("servo reset must lie between start and stop")

    def _validate_all_settings(self):
        servos = self.settings.get("servos", [])
        if not isinstance(servos, list) or not servos:
            raise ValueError("at least one servo definition is required")

        seen_channels = {}
        seen_names = {}
        for index, servo in enumerate(servos):
            self._validate_servo(servo)
            channel = int(servo["channel"])
            name = str(servo["name"])
            if channel in seen_channels:
                raise ValueError("duplicate servo channel: {}".format(channel))
            if name in seen_names:
                raise ValueError("duplicate servo name: {}".format(name))
            seen_channels[channel] = index
            seen_names[name] = index

        pulse_min = float(self.settings["pulse_min_us"])
        pulse_max = float(self.settings["pulse_max_us"])
        if pulse_min >= pulse_max:
            raise ValueError("pulse_min_us must be less than pulse_max_us")

    def _require_ready(self):
        if not self.enabled:
            raise RuntimeError("manager disabled")
        if self.state != self.STATE_OK:
            raise RuntimeError("manager not ready")
        if self.driver is None:
            raise RuntimeError("PCA9685 driver not initialised")

    def _resolve_channel(self, channel_or_name):
        if isinstance(channel_or_name, int):
            channel = int(channel_or_name)
            if channel in self._servos_by_channel:
                return channel
            raise ValueError("servo channel not configured: {}".format(channel))

        text = str(channel_or_name)
        if text.isdigit():
            channel = int(text)
            if channel in self._servos_by_channel:
                return channel
            raise ValueError("servo channel not configured: {}".format(channel))

        servo = self._servos_by_name.get(text)
        if servo is not None:
            return int(servo["channel"])
        raise ValueError("servo not found: {}".format(text))

    def _get_servo(self, channel):
        servo = self._servos_by_channel.get(int(channel))
        if servo is None:
            raise ValueError("servo channel not configured: {}".format(channel))
        return servo

    def _iter_channels(self):
        channels = list(self._servos_by_channel.keys())
        channels.sort()
        return channels

    def _clamp_position(self, position):
        position = float(position)
        if position < 0.0:
            return 0.0
        if position > 1.0:
            return 1.0
        return position

    # --- Mapping -----------------------------------------------------------------

    def _position_to_degrees(self, channel, position):
        position = self._clamp_position(position)
        servo = self._get_servo(channel)
        start_deg = float(servo["start"])
        reset_deg = float(servo["reset"])
        stop_deg = float(servo["stop"])

        if position <= 0.5:
            frac = position / 0.5
            return start_deg + frac * (reset_deg - start_deg)

        frac = (position - 0.5) / 0.5
        return reset_deg + frac * (stop_deg - reset_deg)

    def _degrees_to_position(self, channel, degrees):
        servo = self._get_servo(channel)
        start_deg = float(servo["start"])
        reset_deg = float(servo["reset"])
        stop_deg = float(servo["stop"])
        degrees = float(degrees)

        if degrees <= reset_deg:
            span = reset_deg - start_deg
            if span == 0:
                return 0.5
            pos = (degrees - start_deg) / span
            return max(0.0, min(0.5, pos * 0.5))

        span = stop_deg - reset_deg
        if span == 0:
            return 0.5
        pos = (degrees - reset_deg) / span
        return max(0.5, min(1.0, 0.5 + pos * 0.5))

    def _degrees_to_pulse_us(self, degrees):
        degrees = float(degrees)

        if degrees < -90.0:
            degrees = -90.0
        elif degrees > 90.0:
            degrees = 90.0

        pulse_min = float(self.settings["pulse_min_us"])
        pulse_max = float(self.settings["pulse_max_us"])

        frac = (degrees + 90.0) / 180.0
        return int(pulse_min + frac * (pulse_max - pulse_min))

    # --- Hardware output ----------------------------------------------------------

    def _apply_degrees(self, channel, degrees, publish=True, source="direct"):
        self._require_ready()
        channel = int(channel)
        pulse_us = self._degrees_to_pulse_us(degrees)
        self.driver.set_pulse_us(channel, pulse_us)

        position = self._degrees_to_position(channel, degrees)
        self._runtime[channel]["degrees"] = float(degrees)
        self._runtime[channel]["position"] = float(position)
        self._runtime[channel]["pulse_us"] = float(pulse_us)
        self._get_servo(channel)["position"] = float(position)

        if publish:
            self.events["pca9685.servo_moved"].publish({
                "channel": channel,
                "name": self._get_servo(channel)["name"],
                "position": float(position),
                "degrees": float(degrees),
                "pulse_us": float(pulse_us),
                "source": source,
            })

        return {
            "channel": channel,
            "name": self._get_servo(channel)["name"],
            "position": float(position),
            "degrees": float(degrees),
            "pulse_us": float(pulse_us),
        }

    def _apply_position(self, channel, position, publish=True, source="direct"):
        position = self._clamp_position(position)
        degrees = self._position_to_degrees(channel, position)
        return self._apply_degrees(channel, degrees, publish=publish, source=source)

    def _turn_off(self, channel):
        self._require_ready()
        channel = int(channel)
        self.driver.set_channel_off(channel)
        return {"channel": channel, "name": self._get_servo(channel)["name"], "off": True}

    # --- Persistence / calibration ------------------------------------------------

    def _save_settings(self):
        if hasattr(self.clb, "config") and self.clb.config:
            self.clb.config.save()
        elif hasattr(self.clb, "configurator") and self.clb.configurator:
            self.clb.configurator.save()

    def _capture_field(self, channel, field_name):
        servo = self._get_servo(channel)
        old_value = servo[field_name]
        servo[field_name] = float(self._runtime[channel]["degrees"])
        try:
            self._validate_servo(servo)
        except Exception:
            servo[field_name] = old_value
            raise

        self._save_settings()
        self._apply_position(channel, self._runtime[channel]["position"], publish=False, source="capture")
        payload = {
            "channel": int(channel),
            "name": servo["name"],
            "field": field_name,
            "value": float(servo[field_name]),
        }
        self.events["pca9685.calibration_changed"].publish(payload)
        return payload

    def _set_calibration_field(self, channel, field_name, value):
        servo = self._get_servo(channel)
        old_value = servo[field_name]
        servo[field_name] = float(value)
        try:
            self._validate_servo(servo)
        except Exception:
            servo[field_name] = old_value
            raise

        self._save_settings()
        self._apply_position(channel, self._runtime[channel]["position"], publish=False, source="calibration")
        payload = {
            "channel": int(channel),
            "name": servo["name"],
            "field": field_name,
            "value": float(servo[field_name]),
        }
        self.events["pca9685.calibration_changed"].publish(payload)
        return payload

    # --- Direct service methods ---------------------------------------------------

    def set_position(self, channel, position):
        return self._apply_position(self._resolve_channel(channel), position)

    def set_position_name(self, name, position):
        return self._apply_position(self._resolve_channel(name), position)

    def set_degrees(self, channel, degrees):
        return self._apply_degrees(self._resolve_channel(channel), degrees)

    def set_degrees_name(self, name, degrees):
        return self._apply_degrees(self._resolve_channel(name), degrees)

    def reset(self, channel):
        channel = self._resolve_channel(channel)
        servo = self._get_servo(channel)
        result = self._apply_position(channel, 0.5, source="reset")
        self.events["pca9685.servo_reset"].publish({
            "channel": channel,
            "name": servo["name"],
            "position": result["position"],
            "degrees": result["degrees"],
        })
        return result

    def reset_name(self, name):
        return self.reset(name)

    def reset_all(self):
        results = []
        for channel in self._iter_channels():
            results.append(self.reset(channel))
        self.events["pca9685.reset_all"].publish({"count": len(results)})
        return results

    def off(self, channel):
        return self._turn_off(self._resolve_channel(channel))

    def off_name(self, name):
        return self._turn_off(self._resolve_channel(name))

    def off_all(self):
        results = []
        for channel in self._iter_channels():
            results.append(self._turn_off(channel))
        return results

    def list(self):
        out = []
        for channel in self._iter_channels():
            servo = self._get_servo(channel)
            runtime = self._runtime[channel]
            out.append({
                "channel": channel,
                "name": servo["name"],
                "start": servo["start"],
                "reset": servo["reset"],
                "stop": servo["stop"],
                "position": runtime["position"],
                "degrees": runtime["degrees"],
            })
        return out

    def info(self, channel_or_name):
        channel = self._resolve_channel(channel_or_name)
        servo = self._get_servo(channel)
        runtime = self._runtime[channel]
        return {
            "channel": channel,
            "name": servo["name"],
            "start": servo["start"],
            "reset": servo["reset"],
            "stop": servo["stop"],
            "position": runtime["position"],
            "degrees": runtime["degrees"],
            "pulse_us": runtime["pulse_us"],
        }

    # --- Orchestration services ---------------------------------------------------

    def run(self, orchestration):
        if not isinstance(orchestration, dict):
            raise ValueError("orchestration must be a dict")
        name = orchestration.get("name", "unnamed")
        owner = orchestration.get("owner", self.name)
        steps = orchestration.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError("orchestration.steps must be a non-empty list")

        run = {
            "run_id": self._next_run_id,
            "name": name,
            "owner": owner,
            "steps": steps,
            "step_index": -1,
            "step_started_ms": None,
            "step_runtime": None,
        }
        self._next_run_id += 1
        self._active_runs.append(run)
        self.events["pca9685.orchestration_started"].publish({
            "run_id": run["run_id"],
            "name": name,
            "owner": owner,
            "step_count": len(steps),
        })
        self._start_next_step(run, time.ticks_ms())
        return {"run_id": run["run_id"], "name": name, "owner": owner}

    def run_named(self, name):
        preset = self.settings.get("orchestrations", {}).get(name)
        if preset is None:
            raise ValueError("unknown orchestration: {}".format(name))
        if isinstance(preset, list):
            orch = {"name": name, "owner": self.name, "steps": preset}
        elif isinstance(preset, dict):
            orch = preset.copy()
            orch.setdefault("name", name)
            orch.setdefault("owner", self.name)
        else:
            raise ValueError("stored orchestration must be a list or dict")
        return self.run(orch)

    def stop(self, run_id):
        for i, run in enumerate(self._active_runs):
            if run["run_id"] == int(run_id):
                self._active_runs.pop(i)
                payload = {"run_id": run["run_id"], "name": run["name"], "owner": run["owner"]}
                self.events["pca9685.orchestration_cancelled"].publish(payload)
                return payload
        return None

    def stop_name(self, name):
        for run in list(self._active_runs):
            if run["name"] == name:
                return self.stop(run["run_id"])
        return None

    def stop_all(self):
        stopped = []
        for run in list(self._active_runs):
            payload = self.stop(run["run_id"])
            if payload is not None:
                stopped.append(payload)
        return stopped

    def running(self):
        return [
            {
                "run_id": run["run_id"],
                "name": run["name"],
                "owner": run["owner"],
                "step_index": run["step_index"],
                "step_count": len(run["steps"]),
            }
            for run in self._active_runs
        ]

    def _start_next_step(self, run, now_ms):
        run["step_index"] += 1
        if run["step_index"] >= len(run["steps"]):
            self.events["pca9685.orchestration_completed"].publish({
                "run_id": run["run_id"],
                "name": run["name"],
                "owner": run["owner"],
                "step_count": len(run["steps"]),
                "completed": True,
            })
            return False

        step = run["steps"][run["step_index"]]
        run["step_started_ms"] = now_ms

        if "wait_ms" in step:
            run["step_runtime"] = {
                "type": "wait",
                "wait_ms": int(step["wait_ms"]),
            }
            self.events["pca9685.orchestration_step"].publish({
                "run_id": run["run_id"],
                "name": run["name"],
                "owner": run["owner"],
                "step_index": run["step_index"],
                "step_type": "wait",
            })
            return True

        if "duration_ms" in step and "positions" in step:
            targets = {}
            starts = {}
            for key, pos in step["positions"].items():
                channel = self._resolve_channel(key)
                starts[channel] = float(self._runtime[channel]["position"])
                targets[channel] = float(pos)
            run["step_runtime"] = {
                "type": "move",
                "duration_ms": int(step["duration_ms"]),
                "start_positions": starts,
                "targets": targets,
            }
            self.events["pca9685.orchestration_step"].publish({
                "run_id": run["run_id"],
                "name": run["name"],
                "owner": run["owner"],
                "step_index": run["step_index"],
                "step_type": "move",
                "targets": dict((self._get_servo(channel)["name"], pos) for channel, pos in targets.items()),
            })
            return True

        raise ValueError("unsupported step format")

    def _update_run(self, run, now_ms):
        runtime = run["step_runtime"]
        if runtime is None:
            return False

        elapsed = time.ticks_diff(now_ms, run["step_started_ms"])

        if runtime["type"] == "wait":
            if elapsed >= runtime["wait_ms"]:
                return self._start_next_step(run, now_ms)
            return True

        duration = runtime["duration_ms"]
        if duration <= 0:
            progress = 1.0
        else:
            progress = elapsed / float(duration)
            if progress < 0.0:
                progress = 0.0
            if progress > 1.0:
                progress = 1.0

        for channel, start_pos in runtime["start_positions"].items():
            target_pos = runtime["targets"][channel]
            current_pos = start_pos + (target_pos - start_pos) * progress
            self._apply_position(channel, current_pos, publish=False, source="orchestration")

        if progress >= 1.0:
            for channel, target_pos in runtime["targets"].items():
                self._apply_position(channel, target_pos, publish=True, source="orchestration")
            return self._start_next_step(run, now_ms)

        return True

    # --- Manager callback ---------------------------------------------------------

    def on_setting_changed(self, setting_path, old_value, new_value):
        try:
            if setting_path.startswith("servos["):
                start = setting_path.find("[") + 1
                end = setting_path.find("]")
                index = int(setting_path[start:end])
                field = setting_path[end + 2:]
                servos = self.settings.get("servos", [])
                if index < 0 or index >= len(servos):
                    return

                servo = servos[index]

                if field in ("channel", "name"):
                    self._validate_all_settings()
                    self._build_runtime_cache()
                    return

                channel = int(servo["channel"])

                if field in ("start", "reset", "stop"):
                    self._validate_servo(servo)
                    if self.state == self.STATE_OK:
                        self._apply_position(channel, self._runtime[channel]["position"], publish=False, source="setting")
                    self.events["pca9685.calibration_changed"].publish({
                        "channel": channel,
                        "name": servo["name"],
                        "field": field,
                        "value": float(servo[field]),
                    })
                elif field == "position" and self.state == self.STATE_OK:
                    self._apply_position(channel, servo.get("position", 0.5), publish=True, source="setting")
                return

            if setting_path in ("pwm_frequency", "address", "i2c_bus", "i2c_sda_pin", "i2c_scl_pin"):
                if self.enabled:
                    self.setup(self.settings)
                    self.setup_services()
            elif setting_path in ("pulse_min_us", "pulse_max_us"):
                self._validate_all_settings()
                if self.state == self.STATE_OK:
                    for channel in self._iter_channels():
                        self._apply_position(channel, self._runtime[channel]["position"], publish=False, source="setting")
        except Exception as e:
            print("[pca9685] setting change failed:", e)

    # --- Command wrappers ---------------------------------------------------------

    def command_set_position(self, channel, position):
        return self.set_position(channel, position)

    def command_set_position_name(self, name, position):
        return self.set_position_name(name, position)

    def command_set_degrees(self, channel, degrees):
        return self.set_degrees(channel, degrees)

    def command_set_degrees_name(self, name, degrees):
        return self.set_degrees_name(name, degrees)

    def command_reset(self, channel):
        return self.reset(channel)

    def command_reset_name(self, name):
        return self.reset_name(name)

    def command_reset_all(self):
        return self.reset_all()

    def command_off(self, channel):
        return self.off(channel)

    def command_off_name(self, name):
        return self.off_name(name)

    def command_off_all(self):
        return self.off_all()

    def command_list(self):
        return self.list()

    def command_info(self, channel_or_name):
        return self.info(channel_or_name)

    def command_capture_start(self, channel):
        return self._capture_field(self._resolve_channel(channel), "start")

    def command_capture_reset(self, channel):
        return self._capture_field(self._resolve_channel(channel), "reset")

    def command_capture_stop(self, channel):
        return self._capture_field(self._resolve_channel(channel), "stop")

    def command_capture_start_name(self, name):
        return self._capture_field(self._resolve_channel(name), "start")

    def command_capture_reset_name(self, name):
        return self._capture_field(self._resolve_channel(name), "reset")

    def command_capture_stop_name(self, name):
        return self._capture_field(self._resolve_channel(name), "stop")

    def command_set_start(self, channel, value):
        return self._set_calibration_field(self._resolve_channel(channel), "start", value)

    def command_set_reset(self, channel, value):
        return self._set_calibration_field(self._resolve_channel(channel), "reset", value)

    def command_set_stop(self, channel, value):
        return self._set_calibration_field(self._resolve_channel(channel), "stop", value)

    def command_set_start_name(self, name, value):
        return self._set_calibration_field(self._resolve_channel(name), "start", value)

    def command_set_reset_name(self, name, value):
        return self._set_calibration_field(self._resolve_channel(name), "reset", value)

    def command_set_stop_name(self, name, value):
        return self._set_calibration_field(self._resolve_channel(name), "stop", value)

    def command_run(self, orchestration):
        return self.run(orchestration)

    def command_run_named(self, name):
        return self.run_named(name)

    def command_stop(self, run_id):
        return self.stop(run_id)

    def command_stop_name(self, name):
        return self.stop_name(name)

    def command_stop_all(self):
        return self.stop_all()

    def command_running(self):
        return self.running()
