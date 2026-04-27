# Eye Manager

Controls a pair of servo-driven googly eyes. Manages six servos — left/right gaze, up/down gaze, and four eyelids — via the [PCA9685 Manager](pca9685_manager.md). Supports direct look/pose commands, blinking, named orchestrations, and an autonomous idle animation that randomly saccades and blinks.

## Dependencies

- `pca9685` — must be enabled and have six named servos configured (see Required Servos below)

## Required Servo Names

The PCA9685 manager must have servos with exactly these names:

| Name | Purpose |
|------|---------|
| `eyes.lr` | Left/right gaze (shared by both eyes) |
| `eyes.ud` | Up/down gaze (shared by both eyes) |
| `left.upperlid` | Left eye upper eyelid |
| `left.lowerlid` | Left eye lower eyelid |
| `right.upperlid` | Right eye upper eyelid |
| `right.lowerlid` | Right eye lower eyelid |

All position values are in the 0.0–1.0 range where 0.5 is the servo's configured reset angle.

## Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable this manager |
| `centre_x` | float | `0.5` | Logical X position for the centred gaze |
| `centre_y` | float | `0.5` | Logical Y position for the centred gaze |
| `normal_open` | float | `0.5` | Default eyelid openness (0.0 = closed, 1.0 = wide open) |
| `blink_closed_open` | float | `0.0` | Eyelid position during the closed phase of a blink |
| `blink_close_ms` | int | `70` | Time in ms to close the eyes during a blink |
| `blink_hold_ms` | int | `25` | Time in ms to hold eyes closed |
| `blink_open_ms` | int | `90` | Time in ms to re-open eyes after a blink |
| `default_move_ms` | int | `100` | Default movement duration when none is specified |
| `idle_animation` | bool | `false` | Start the idle animation loop on startup |
| `idle_min_gap_ms` | int | `1500` | Minimum ms between idle movements |
| `idle_max_gap_ms` | int | `5000` | Maximum ms between idle movements |
| `idle_blink_chance` | float | `0.35` | Probability that each idle step is a blink (vs. a saccade) |
| `idle_saccade_min_ms` | int | `50` | Minimum duration for an idle saccade movement |
| `idle_saccade_max_ms` | int | `140` | Maximum duration for an idle saccade movement |
| `idle_return_chance` | float | `0.35` | Probability that an idle saccade returns to centre |
| `idle_max_offset_x` | float | `0.35` | Maximum X offset from centre during idle saccades |
| `idle_max_offset_y` | float | `0.25` | Maximum Y offset from centre during idle saccades |
| `idle_open_jitter` | float | `0.0` | Random eyelid variation applied during idle saccades |
| `orchestrations` | dict | `{}` | Named pose/blink/step presets (see Named Orchestrations) |

## Services

| Command | Syntax | Description |
|---------|--------|-------------|
| `look` | `look <x> <y> [duration_ms]` | Move gaze to (x, y); values 0.0–1.0 |
| `open` | `open <amount> [duration_ms]` | Set eyelid openness; 0.0 = closed, 1.0 = wide open |
| `pose` | `pose <x> <y> <open> [duration_ms]` | Set gaze and eyelid openness in one command |
| `centre` | `centre [duration_ms]` | Return gaze to the configured centre position |
| `blink` | `blink` | Perform a single blink using the configured blink timings |
| `run` | `run <name>` | Run a named orchestration from settings |
| `stop` | `stop` | Cancel the currently running animation |
| `start_idle` | `start_idle` | Start the autonomous idle animation loop |
| `stop_idle` | `stop_idle` | Stop the autonomous idle animation loop |
| `status` | `status` | Print current pose, active run, and idle state |

## Events

| Event | Payload | Description |
|-------|---------|-------------|
| `eye.pose_changed` | `x`, `y`, `open` | The stored eye pose was updated |
| `eye.animation_started` | `name`, `run_id`, `pose` | An animation or orchestration started |
| `eye.animation_completed` | (from pca9685) | The current animation completed |
| `eye.animation_cancelled` | (from pca9685) | The current animation was cancelled |
| `eye.animation_error` | (from pca9685) | The current animation failed |
| `eye.blink_completed` | (from pca9685) | A blink animation completed |
| `eye.idle_started` | `startup`, `next_ms` | Idle animation was enabled |
| `eye.idle_stopped` | `active_run` | Idle animation was disabled |
| `eye.idle_step` | `kind`, `run_id`, (saccade: `x`, `y`, `open`, `duration_ms`) | The idle loop launched a movement |

## Named Orchestrations

Named orchestrations are stored in the `orchestrations` settings key. Three formats are supported:

**Pose** — move to a fixed gaze position:
```json
"look_left": {
    "type": "pose",
    "x": 0.2,
    "y": 0.5,
    "open": 0.5,
    "duration_ms": 150
}
```

**Blink** — blink with custom timings:
```json
"slow_blink": {
    "type": "blink",
    "blink_close_ms": 200,
    "blink_hold_ms": 100,
    "blink_open_ms": 200
}
```

**Steps** — full multi-step orchestration passed directly to the PCA9685:
```json
"suspicious": {
    "steps": [
        { "duration_ms": 150, "positions": { "left.upperlid": 0.3, "right.upperlid": 0.3 } },
        { "wait_ms": 500 },
        { "duration_ms": 150, "positions": { "left.upperlid": 0.5, "right.upperlid": 0.5 } }
    ]
}
```

## Example Settings

```json
{
    "pca9685": {
        "enabled": true,
        "i2c_bus": 0,
        "i2c_sda_pin": 4,
        "i2c_scl_pin": 5,
        "pwm_frequency": 50,
        "servos": [
            { "channel": 0, "name": "eyes.lr",       "start": -45, "reset": 0, "stop": 45 },
            { "channel": 1, "name": "eyes.ud",        "start": -20, "reset": 0, "stop": 20 },
            { "channel": 2, "name": "left.upperlid",  "start": -30, "reset": 0, "stop": 30 },
            { "channel": 3, "name": "left.lowerlid",  "start": -30, "reset": 0, "stop": 30 },
            { "channel": 4, "name": "right.upperlid", "start": -30, "reset": 0, "stop": 30 },
            { "channel": 5, "name": "right.lowerlid", "start": -30, "reset": 0, "stop": 30 }
        ]
    },
    "eye": {
        "enabled": true,
        "centre_x": 0.5,
        "centre_y": 0.5,
        "normal_open": 0.5,
        "idle_animation": true,
        "idle_blink_chance": 0.4,
        "orchestrations": {
            "look_left":  { "type": "pose", "x": 0.15, "y": 0.5 },
            "look_right": { "type": "pose", "x": 0.85, "y": 0.5 },
            "wink":       { "type": "blink", "blink_close_ms": 120, "blink_hold_ms": 300, "blink_open_ms": 120 }
        }
    }
}
```
