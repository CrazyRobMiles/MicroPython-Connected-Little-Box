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
| `pullup` | bool | false | Global default for pull-up resistor on input pins |

## Input Pin Configuration

Each input pin requires:

| Setting | Type | Description |
|---------|------|-------------|
| `name` | string | Unique pin identifier |
| `pin` | int | GPIO pin number |
| `debounce_ms` | int | Debounce time in ms (uses `default_debounce_ms` if omitted) |
| `pullup` | bool | Enable pull-up resistor for this pin (overrides global default) |

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
| `set <pin_name> <state>` | Set output pin to 0 (low) or 1 (high) |
| `get <pin_name>` | Read current state of an input or output pin |
| `list` | List all configured input and output pins with their current states |

## Events

For each configured input pin named `{name}`, two events are published on state transitions:

| Event | Description |
|-------|-------------|
| `gpio.<name>_high` | Pin transitioned from low to high |
| `gpio.<name>_low` | Pin transitioned from high to low |

These events are used by other managers (such as the [Tilt Manager](tilt_manager.md)) to react to hardware signals.

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
gpio.set relay_1 1
gpio.set relay_1 0
gpio.get button_a
gpio.list
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
