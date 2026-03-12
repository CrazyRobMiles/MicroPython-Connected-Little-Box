[← Back to README](../../README.md)

# Stepper Manager

Controls 1-4 stepper motors (28BYJ-48 with ULN2003 drivers) for movement and rotation control.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | false | Enable/disable stepper control |
| `motors` | array | 4 empty motors | Motor configuration array |
| `motors[].pins` | array | [-1,-1,-1,-1] | GPIO pins [IN1, IN2, IN3, IN4] (-1 = unused) |
| `motors[].wheel_diameter_mm` | float | 69.0 | Wheel diameter in millimeters |
| `wheel_spacing_mm` | float | 110.0 | Center-to-center distance between left/right wheels |
| `steps_per_rev` | int | 4096 | Half-step count per revolution (28BYJ-48: 4096) |
| `min_step_delay_us` | int | 1200 | Minimum step delay in microseconds (affects max speed) |

## Services (Commands)

| Service | Description |
|---------|-------------|
| `move <distance_mm>` | Move forward/backward specified distance |
| `rotate <degrees>` | Rotate specified degrees |
| `arc <radius_mm> <degrees>` | Move in circular arc |
| `stop` | Stop all motors immediately |

## Events

This manager does not emit any events.

## Dependencies

This manager has no dependencies.

## States

- `ready` - Motors initialized and ready for movement
- `moving` - Motors are currently moving
- `error` - Motor initialization error
- `disabled` - Stepper manager is disabled

## Motor Configuration

Each motor requires 4 GPIO pins for control:
- **IN1**: Pin for coil 1
- **IN2**: Pin for coil 2
- **IN3**: Pin for coil 3
- **IN4**: Pin for coil 4

Use -1 for unused motors.

## Example Settings

```json
{
    "stepper": {
        "enabled": true,
        "motors": [
            {
                "pins": [2, 3, 4, 5],
                "wheel_diameter_mm": 69.0
            },
            {
                "pins": [6, 7, 8, 9],
                "wheel_diameter_mm": 69.0
            },
            {
                "pins": [-1, -1, -1, -1],
                "wheel_diameter_mm": 69.0
            },
            {
                "pins": [-1, -1, -1, -1],
                "wheel_diameter_mm": 69.0
            }
        ],
        "wheel_spacing_mm": 110.0,
        "steps_per_rev": 4096,
        "min_step_delay_us": 1200
    }
}
```

## Console Usage

```
stepper.move 100
stepper.rotate 90
stepper.arc 200 45
stepper.stop
```

## Code Usage

```python
# Get the stepper manager instance
stepper = clb.get_service_handle("stepper")

# Move forward 100mm
stepper.move(100)

# Rotate 90 degrees
stepper.rotate(90)

# Move in arc (200mm radius, 45 degrees)
stepper.arc(200, 45)

# Stop all motors
stepper.stop()

# Check if moving
if stepper._moving_any:
    print("Motors are moving")te 90
stepper.arc 200 45
stepper.stop
```

## Notes

- Uses 8-step half-step sequence for smooth motion
- Cross-platform support: Pico (rp2) and ESP32 via compat.py
- Timers are platform-specific (high-resolution on Pico, ms-based on ESP32)
- All motor motion is calculated from wheel diameter and spacing
- Motors are powered down (coils de-energized) when not moving

---

[↑ Back to README](../../README.md)
