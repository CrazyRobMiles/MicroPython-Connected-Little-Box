[← Back to README](../../README.md)

# Lamp Manager

A rotary-encoder-controlled RGB lamp application. Uses the Pixel Manager to drive an LED strip and two Rotary Encoder inputs to let a user adjust colour (hue) and brightness in real time.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | false | Enable/disable the lamp app |
| `default_red` | int | 255 | Initial red component (0–255) |
| `default_green` | int | 255 | Initial green component (0–255) |
| `default_blue` | int | 255 | Initial blue component (0–255) |
| `default_brightness` | float | 1.0 | Initial brightness (0.0–1.0) |
| `color_encoder_name` | string | "color" | Name of the rotary encoder used for hue control |
| `brightness_encoder_name` | string | "brightness" | Name of the rotary encoder used for brightness control |
| `brightness_step` | float | 0.05 | Amount to change brightness per encoder click |
| `color_hue_step` | int | 5 | Degrees of hue to advance per encoder click |

## Services (Commands)

This manager provides no console commands.

## Events

This manager does not emit any events.

## Dependencies

- `pixel` — LED strip display
- `rotary_encoder` — Two encoder entries must be configured with names matching `color_encoder_name` and `brightness_encoder_name`

## States

- `ok` - Lamp app running
- `disabled` - Lamp app is disabled

## How It Works

On startup the manager subscribes to clockwise and anticlockwise events from both configured encoders:

- **Color encoder** — advances or retreats the HSV hue, converting to RGB and applying it to the full LED strip
- **Brightness encoder** — increases or decreases the brightness multiplier, clamped to 0.0–1.0

## Example Settings

```json
{
    "pixel": {
        "enabled": true,
        "pixelpin": 18,
        "panel_width": 8,
        "panel_height": 8,
        "x_panels": 1,
        "y_panels": 1
    },
    "rotary_encoder": {
        "enabled": true,
        "encoders": [
            { "name": "color",      "clk_pin": 16, "dt_pin": 17, "btn_pin": -1 },
            { "name": "brightness", "clk_pin": 19, "dt_pin": 20, "btn_pin": -1 }
        ]
    },
    "App_lamp": {
        "enabled": true,
        "default_red": 255,
        "default_green": 200,
        "default_blue": 100,
        "default_brightness": 0.8,
        "color_encoder_name": "color",
        "brightness_encoder_name": "brightness",
        "brightness_step": 0.05,
        "color_hue_step": 5
    }
}
```

---

[↑ Back to README](../../README.md)
