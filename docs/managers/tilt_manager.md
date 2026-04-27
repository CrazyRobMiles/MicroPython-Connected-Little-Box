# Tilt Manager

Interprets events from a tilt ball-switch (connected via the GPIO Manager) as higher-level gestures. Detects tip-and-hold, individual pulses (brief tilts), and sequences of pulses, with short/long pulse classification.

The manager consumes `gpio.<src>_high` and `gpio.<src>_low` events rather than reading a pin directly, so a GPIO Manager entry must be configured for the tilt switch.

## Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable this manager |
| `src_gpio` | str | `"tilt"` | Name of the GPIO manager entry that reads the tilt switch — subscribes to `gpio.<src_gpio>_high` and `gpio.<src_gpio>_low` |
| `rest_calibrate_ms` | int | `2000` | How long the switch must be still before its current state is latched as "rest" |
| `hold_ms` | int | `700` | How long the device must stay tipped before a `tipped` event fires |
| `pulse_min_ms` | int | `150` | Minimum tilt duration to count as a pulse (shorter tilts are ignored) |
| `pulse_max_ms` | int | `2500` | Maximum tilt duration to count as a pulse (longer tilts fire `tipped` instead) |
| `long_ms` | int | `1000` | Pulse duration threshold: pulses ≥ this are classified as `long`, shorter as `short` |
| `max_intertap_ms` | int | `700` | Maximum gap between pulse ends for pulses to be grouped into the same sequence |
| `end_gap_ms` | int | `800` | Silence after the last pulse before the sequence is published |

## Events

| Event | Payload | Description |
|-------|---------|-------------|
| `tilt.tipped` | `t_ms`, `held_ms`, `src_gpio` | Device has been held away from rest for `hold_ms` |
| `tilt.returned` | `src_gpio` | Device returned to rest after a `tipped` event |
| `tilt.pulse` | `t_ms`, `width_ms`, `src_gpio` | A complete tip-and-return pulse within the min/max window |
| `tilt.short` | `t_ms`, `width_ms`, `src_gpio` | Pulse shorter than `long_ms` |
| `tilt.long` | `t_ms`, `width_ms`, `src_gpio` | Pulse at least `long_ms` in duration |
| `tilt.sequence` | `t_ms`, `count`, `short`, `long`, `src_gpio` | A sequence of pulses ended; `count` is total pulses, `short`/`long` are counts of each type |

## Dependencies

- `gpio` — a GPIO Manager entry named `src_gpio` must be configured for the tilt switch pin

## States

| State | Description |
|-------|-------------|
| `ok` | Running; waiting for rest state to be calibrated |
| `disabled` | Manager is disabled |

## Notes

- On startup the manager waits for `rest_calibrate_ms` of silence before it starts classifying gestures. This allows it to learn the switch's natural resting position regardless of which way up the device is mounted.
- `tipped` fires when the device is held tipped for longer than `hold_ms`. Pulses shorter than `pulse_max_ms` that complete before `hold_ms` elapses are classified as normal pulses and do not generate a `tipped` event.
- The `sequence` event is the most useful for detecting Morse-style input patterns using `short` and `long` counts.

## Example Settings

```json
{
    "gpio": {
        "enabled": true,
        "pins": [
            {
                "name": "tilt",
                "pin": 16,
                "mode": "input",
                "pullup": true
            }
        ]
    },
    "tilt": {
        "enabled": true,
        "src_gpio": "tilt",
        "rest_calibrate_ms": 2000,
        "hold_ms": 700,
        "pulse_min_ms": 150,
        "pulse_max_ms": 2500,
        "long_ms": 1000,
        "max_intertap_ms": 700,
        "end_gap_ms": 800
    }
}
```
