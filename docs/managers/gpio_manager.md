[← Back to README](../../README.md)

# GPIO Manager

Manages general-purpose input and output pins for digital control and sensing.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | false | Enable/disable GPIO management |
| `input_pins` | array | [] | Array of input pin configurations |
| `output_pins` | array | [] | Array of output pin configurations |
| `default_debounce_ms` | int | 20 | Default debounce time for input pins |

## Input Pin Configuration

Each input pin requires:

| Setting | Type | Description |
|---------|------|-------------|
| `name` | string | Unique pin identifier |
| `pin` | int | GPIO pin number |
| `debounce_ms` | int | Debounce time (uses default if omitted) |

## Output Pin Configuration

Each output pin requires:

| Setting | Type | Description |
|---------|------|-------------|
| `name` | string | Unique pin identifier |
| `pin` | int | GPIO pin number |
| `initial_state` | int | Initial state: 0 (low) or 1 (high) |

## Services (Commands)

| Service | Description |
|---------|-------------|
| `set_output <pin_name> <state>` | Set output pin (0 or 1) |
| `get_input <pin_name>` | Read input pin state |

## Events

This manager can emit state change events for input pins (subscribe via application).

## Dependencies

This manager has no dependencies.

## States

- `ok` - GPIO initialized and ready
- `error` - Initialization error
- `disabled` - GPIO manager is disabled

## Example Settings

```json
{
    "gpio": {
        "enabled": true,
        "default_debounce_ms": 20,
        "input_pins": [
            {
                "name": "button_a",
                "pin": 14,
                "debounce_ms": 20
            },
            {
                "name": "button_b",
                "pin": 15
            }
        ],
        "output_pins": [
            {
                "name": "relay_1",
                "pin": 10,
                "initial_state": 0
            },
            {
                "name": "status_led",
                "pin": 11,
                "initial_state": 1
            }
        ]
    }
}
```

## Console Usage

```
gpio.set_output relay_1 1
gpio.set_output relay_1 0
gpio.get_input button_a
```

## Code Usage

```python
# Get the GPIO manager instance
gpio = clb.get_service_handle("gpio")

# Set output pin high
gpio.set_output("relay_1", 1)

# Set output pin low
gpio.set_output("relay_1", 0)

# Read input pin
state = gpio.input_pins["button_a"]["pin"].value()
print(f"Button A state: {state}")

# Check last state
last_state = gpio.input_pins["button_a"]["last_state"]
print(f"Last button state: {last_state}") 1
gpio.set_output relay_1 0
gpio.get_input button_a
```

## GPIO Pin Mapping (Raspberry Pi Pico)

GPIO pins are numbered 0-28 on the Pico:
- GP0-GP7: General purpose
- GP8-GP13: Generally available
- GP14-GP22: Generally available
- GP23-GP25: Special functions (avoid)
- GP26-GP29: ADC inputs (can use as GPIO)

## Notes

- Input pins use configurable debouncing to eliminate switch bounce
- Output pins can be set to any GPIO pin
- Initial state applies when the pin is first configured
- State changes for input pins can be monitored by subscribing to events
- Each input pin tracks last state and change timestamp for debouncing

---

[↑ Back to README](../../README.md)
