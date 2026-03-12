[← Back to README](../../README.md)

# Rotary Encoder Manager

Manages rotary encoders with button support for user input control.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | false | Enable/disable rotary encoder support |
| `encoders` | array | [] | Array of encoder configurations |

## Encoder Configuration

Each encoder in the `encoders` array requires:

| Setting | Type | Description |
|---------|------|-------------|
| `name` | string | Unique encoder identifier |
| `clk_pin` | int | GPIO pin for CLK (clock) |
| `dt_pin` | int | GPIO pin for DT (data/direction) |
| `btn_pin` | int | GPIO pin for button (optional, -1 to disable) |

## Services (Commands)

This manager does not provide console commands.

## Events

For each configured encoder named `{name}`, the following events are emitted:

| Event | Description |
|-------|-------------|
| `rotary_encoder.{name}_connected` | Encoder connected |
| `rotary_encoder.{name}_moved_clockwise` | Rotated clockwise |
| `rotary_encoder.{name}_moved_anticlockwise` | Rotated counter-clockwise |
| `rotary_encoder.{name}_button_pressed` | Button pressed (if configured) |

## Dependencies

This manager has no dependencies.

## States

- `ok` - Encoders initialized and ready
- `disabled` - Rotary encoder support is disabled

## Example Settings

```json
{
    "rotary_encoder": {
        "enabled": true,
        "encoders": [
            {
                "name": "main_control",
                "clk_pin": 16,
                "dt_pin": 17,
                "btn_pin": 18
            },
            {
                "name": "secondary_control",
                "clk_pin": 19,
                "dt_pin": 20,
                "btn_pin": -1
            }
        ]
    }
}
```

## Code Usage

```python
# Get the rotary encoder manager instance
encoder = clb.get_service_handle("rotary_encoder")

# Subscribe to encoder events
event = clb.get_event("rotary_encoder.main_control_moved_clockwise")
if event:
    event.subscribe(on_clockwise)

event = clb.get_event("rotary_encoder.main_control_moved_anticlockwise")
if event:
    event.subscribe(on_anticlockwise)

event = clb.get_event("rotary_encoder.main_control_button_pressed")
if event:
    event.subscribe(on_button)

def on_clockwise(event_data):
    print("Rotated clockwise")

def on_anticlockwise(event_data):
    print("Rotated counter-clockwise")

def on_button(event_data):
    print("Button pressed")
```

## 

## Rotary Encoder Hardware

Standard rotary encoders have 3 pins:
- **CLK** (Clock): Rotated signal pulse
- **DT** (Data/Direction): Direction indicator
- **Button** (optional): Push-to-click switch

## Rotation Detection

The manager uses the following logic:
- **Clockwise**: CLK and DT transitions in one pattern
- **Counter-clockwise**: CLK and DT transitions in opposite pattern
- Debouncing is handled automatically

## Notes

- Each encoder is independently configurable
- Button pins are optional (-1 disables button for that encoder)
- Encoders emit events that other managers can subscribe to
- Multiple encoders can be configured and used simultaneously
- Debouncing prevents false triggers from contact bounce

---

[↑ Back to README](../../README.md)
