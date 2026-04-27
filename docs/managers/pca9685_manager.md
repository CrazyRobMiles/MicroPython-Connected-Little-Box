# PCA9685 Manager

Controls a PCA9685 16-channel I2C PWM driver, typically used to drive servo motors. Supports named servos, calibrated position ranges, direct position/degree commands, and multi-servo orchestrations (animated sequences with interpolated movement).

## Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable this manager |
| `i2c_bus` | int | `0` | I2C bus number |
| `i2c_sda_pin` | int | `4` | SDA pin number |
| `i2c_scl_pin` | int | `5` | SCL pin number |
| `address` | int | `0x40` | I2C address of the PCA9685 |
| `pwm_frequency` | int | `50` | PWM frequency in Hz (50 Hz for standard servos) |
| `pulse_min_us` | int | `500` | Pulse width in µs corresponding to the minimum servo angle |
| `pulse_max_us` | int | `2500` | Pulse width in µs corresponding to the maximum servo angle |
| `move_on_setup` | bool | `true` | Move all servos to their reset positions on startup |
| `servos` | list | `[]` | List of servo definitions (see below) |
| `orchestrations` | dict | `{}` | Named orchestration presets (see below) |

### Servo definition

Each entry in `servos` must have:

| Key | Type | Description |
|-----|------|-------------|
| `channel` | int | PCA9685 channel (0–15) |
| `name` | str | Logical name used in commands and orchestrations |
| `start` | float | Degrees at logical position 0.0 |
| `reset` | float | Degrees at logical position 0.5 (the resting/neutral position) |
| `stop` | float | Degrees at logical position 1.0 |
| `position` | float | Optional: initial logical position (0.0–1.0), defaults to 0.5 |

Logical position 0.5 always maps to the `reset` angle. This lets you define an asymmetric range while keeping a consistent neutral point.

## Services

| Command | Syntax | Description |
|---------|--------|-------------|
| `set_position` | `set_position <channel> <0..1>` | Move servo on channel to a logical position |
| `set_position_name` | `set_position_name <name> <0..1>` | Move named servo to a logical position |
| `set_degrees` | `set_degrees <channel> <degrees>` | Move servo on channel to an absolute degree value |
| `set_degrees_name` | `set_degrees_name <name> <degrees>` | Move named servo to an absolute degree value |
| `reset` | `reset <channel>` | Move servo to its configured reset position (0.5) |
| `reset_name` | `reset_name <name>` | Move named servo to its reset position |
| `reset_all` | `reset_all` | Move all servos to their reset positions |
| `off` | `off <channel>` | De-energise servo on channel (PWM off) |
| `off_name` | `off_name <name>` | De-energise named servo |
| `off_all` | `off_all` | De-energise all servos |
| `list` | `list` | Show all configured servos and their current state |
| `info` | `info <channel\|name>` | Show detailed info for one servo |
| `run` | `run <orchestration_dict>` | Run an orchestration defined as a dict |
| `run_named` | `run_named <name>` | Run a named orchestration preset |
| `stop` | `stop <run_id>` | Cancel a running orchestration by ID |
| `stop_name` | `stop_name <name>` | Cancel a running orchestration by name |
| `stop_all` | `stop_all` | Cancel all running orchestrations |
| `running` | `running` | List currently active orchestrations |

### Calibration commands

These commands adjust the `start`, `reset`, or `stop` degree values for a servo and persist the change to `settings.json`.

| Command | Description |
|---------|-------------|
| `capture_start <channel>` | Save the servo's current degree position as its `start` value |
| `capture_reset <channel>` | Save current position as `reset` |
| `capture_stop <channel>` | Save current position as `stop` |
| `capture_start_name <name>` | Same as above, by name |
| `capture_reset_name <name>` | Same as above, by name |
| `capture_stop_name <name>` | Same as above, by name |
| `set_start <channel> <degrees>` | Set `start` to an explicit degree value |
| `set_reset <channel> <degrees>` | Set `reset` to an explicit degree value |
| `set_stop <channel> <degrees>` | Set `stop` to an explicit degree value |
| `set_start_name <name> <degrees>` | Same as above, by name |
| `set_reset_name <name> <degrees>` | Same as above, by name |
| `set_stop_name <name> <degrees>` | Same as above, by name |

## Events

| Event | Payload | Description |
|-------|---------|-------------|
| `pca9685.servo_moved` | `channel`, `name`, `position`, `degrees`, `pulse_us`, `source` | A servo was moved |
| `pca9685.servo_reset` | `channel`, `name`, `position`, `degrees` | A servo was reset to its neutral position |
| `pca9685.reset_all` | `count` | All servos were reset |
| `pca9685.calibration_changed` | `channel`, `name`, `field`, `value` | A calibration value (start/reset/stop) changed |
| `pca9685.orchestration_started` | `run_id`, `name`, `owner`, `step_count` | An orchestration started |
| `pca9685.orchestration_step` | `run_id`, `name`, `owner`, `step_index`, `step_type` | An orchestration moved to the next step |
| `pca9685.orchestration_completed` | `run_id`, `name`, `owner`, `step_count` | An orchestration finished all steps |
| `pca9685.orchestration_cancelled` | `run_id`, `name`, `owner` | An orchestration was cancelled |
| `pca9685.orchestration_error` | `run_id`, `name`, `owner`, `error` | An orchestration failed |

## Orchestrations

An orchestration is a list of steps. Each step is either a timed movement or a wait:

```json
{
    "name": "wave",
    "owner": "my_app",
    "steps": [
        { "duration_ms": 300, "positions": { "arm": 0.8 } },
        { "wait_ms": 100 },
        { "duration_ms": 300, "positions": { "arm": 0.5 } }
    ]
}
```

Positions are interpolated smoothly over `duration_ms`. Multiple servos can move simultaneously within a single step. Named presets go in the `orchestrations` settings key.

## Dependencies

None.

## Example Settings

```json
{
    "pca9685": {
        "enabled": true,
        "i2c_bus": 0,
        "i2c_sda_pin": 4,
        "i2c_scl_pin": 5,
        "pwm_frequency": 50,
        "pulse_min_us": 500,
        "pulse_max_us": 2500,
        "servos": [
            {
                "channel": 0,
                "name": "pan",
                "start": -60,
                "reset": 0,
                "stop": 60
            },
            {
                "channel": 1,
                "name": "tilt",
                "start": -30,
                "reset": 0,
                "stop": 45
            }
        ],
        "orchestrations": {
            "nod": [
                { "duration_ms": 200, "positions": { "tilt": 0.8 } },
                { "wait_ms": 100 },
                { "duration_ms": 200, "positions": { "tilt": 0.5 } }
            ]
        }
    }
}
```
