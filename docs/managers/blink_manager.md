[← Back to README](../../README.md)

# Blink Manager

Controls a GPIO pin (typically the built-in LED) with configurable blinking patterns.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | true | Enable/disable the manager |
| `pin` | string/int | "LED" | GPIO pin name ("LED") or number (e.g., 25) |
| `delay_seconds` | float | 1.0 | Interval in seconds between on/off states |

## Services (Commands)

| Service | Description |
|---------|-------------|
| `start` | Start the blinking pattern |
| `stop` | Stop blinking and turn LED off |

## Events

This manager does not emit any events.

## Dependencies

This manager has no dependencies.

## Example Settings

```json
{
    "blink": {
        "enabled": true,
        "pin": "LED",
        "delay_seconds": 1.0
    }
}
```

## Console Usage

```
blink.start
blink.stop
```

## Code Usage

```python
# Get the blink manager instance
blink = clb.get_service_handle("blink")

# Start blinking
blink.start()

blink.start
blink.stop
```

## Notes

- The blink manager uses Python coroutines (`yield`) to avoid blocking the main loop
- The LED is automatically turned off when the manager stops or when it is disabled
- The `delay_seconds` setting controls both the on and off duration

---

[↑ Back to README](../../README.md)
