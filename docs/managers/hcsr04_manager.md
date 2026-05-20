[← Back to README](../../README.md)

# HC-SR04 Distance Sensor Manager

Measures distances using an HC-SR04 ultrasonic sensor. The echo pin uses interrupts to time the return pulse, which is converted to millimetres. Readings are triggered at a configurable interval and published as events. Threshold crossing events fire when the measured distance moves from one side of a configured value to the other.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | false | Enable/disable the manager |
| `trigger_pin` | int | 5 | GPIO pin number connected to the sensor TRIG pin |
| `echo_pin` | int | 18 | GPIO pin number connected to the sensor ECHO pin |
| `interval_ms` | int | 500 | Time between readings in milliseconds |
| `threshold_mm` | int | 300 | Distance threshold in millimetres for crossing events |

## Services (Commands)

| Command | Description |
|---------|-------------|
| `hcsr04.start()` | Begin taking readings at the configured interval |
| `hcsr04.stop()` | Stop taking readings |
| `hcsr04.reading()` | Print the most recent distance in millimetres |
| `hcsr04.set_interval(ms)` | Change the reading interval at runtime |
| `hcsr04.set_threshold(mm)` | Change the distance threshold at runtime |

## Events

| Event | Payload | Description |
|-------|---------|-------------|
| `hcsr04.reading` | `{"distance_mm": int, "duration_us": int}` | Published for every completed reading |
| `hcsr04.below_threshold` | `{"distance_mm": int, "threshold_mm": int}` | Fires once when distance crosses *down* through the threshold |
| `hcsr04.above_threshold` | `{"distance_mm": int, "threshold_mm": int}` | Fires once when distance crosses *up* through the threshold |

The threshold crossing events are edge events — they fire on the transition only, not continuously while the distance remains on one side.

## Dependencies

This manager has no dependencies.

## States

- `ok` — Sensor initialised and ready
- `error` — Initialisation failed (check pin numbers)
- `disabled` — Manager is disabled in settings

## Wiring

| HC-SR04 Pin | Connect to |
|-------------|------------|
| VCC | 5V |
| GND | GND |
| TRIG | `trigger_pin` GPIO |
| ECHO | `echo_pin` GPIO (see note below) |

> **Important:** The HC-SR04 ECHO pin outputs 5V logic. The Raspberry Pi Pico GPIO pins are 3.3V tolerant only. Use a voltage divider (e.g. 1kΩ and 2kΩ resistors) or a level shifter on the ECHO line to protect the Pico.

## Example Settings

```json
{
    "hcsr04": {
        "enabled": true,
        "trigger_pin": 5,
        "echo_pin": 18,
        "interval_ms": 500,
        "threshold_mm": 300
    }
}
```

## Console Usage

```
hcsr04.start()
hcsr04.reading()
hcsr04.set_interval(200)
hcsr04.set_threshold(500)
hcsr04.stop()
```

## Subscribing to Events

```python
def setup_services(self):
    self.clb.get_event("hcsr04.reading").subscribe(self.on_reading)
    self.clb.get_event("hcsr04.below_threshold").subscribe(self.on_close)
    self.clb.get_event("hcsr04.above_threshold").subscribe(self.on_far)

def on_reading(self, event, data):
    print(data["distance_mm"])  # mm

def on_close(self, event, data):
    # object moved closer than threshold_mm
    pass

def on_far(self, event, data):
    # object moved further than threshold_mm
    pass
```

## Notes

- The sensor must be started with `hcsr04.start()` before readings are taken.
- `interval_ms` and `threshold_mm` can be changed at runtime without restarting.
- Changing the threshold resets crossing detection so the next reading re-establishes which side the distance is on.
- Measurements that do not return an echo within 50ms (out of range or no object) are silently discarded.
- The useful range of the HC-SR04 is approximately 20mm to 4000mm.

---

[↑ Back to README](../../README.md)
