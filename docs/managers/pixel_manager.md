[← Back to README](../../README.md)

# Pixel Manager

Controls addressable RGB LED strips (NeoPixel/WS2812B) with animation support and pixel graphics.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | true | Enable/disable pixel display |
| `pixelpin` | int | 18 | GPIO pin for pixel data |
| `panel_width` | int | 8 | Width of pixel panel(s) |
| `panel_height` | int | 8 | Height of pixel panel(s) |
| `x_panels` | int | 3 | Number of panels horizontally |
| `y_panels` | int | 2 | Number of panels vertically |
| `brightness` | float | 1.0 | Brightness multiplier (0.0-1.0) |
| `pixeltype` | string | "RGB" | Pixel color format (RGB, GRB, etc.) |
| `animation` | string | "None" | Animation name or "None" to disable |
| `panel_type` | string | "Multi-panels-x" | Panel arrangement type |

## Services (Commands)

| Service | Description |
|---------|-------------|
| `on` | Enable pixel display |
| `stop` | Stop animation |
| `test` | Display test pattern (fills all pixels) |
| `raw_test` | Test individual pixel control |
| `fill <r> <g> <b>` | Fill display with solid color |
| `set_rgb <x> <y> <r> <g> <b>` | Set individual pixel color |
| `animate` | Start configured animation |
| `show` | Refresh pixel display |
| `clock` | Display time on pixels |
| `show_text <x> <y> <r> <g> <b> "message"` | Display scrolling text |

## Events

This manager does not emit any events.

## Dependencies

This manager has no dependencies.

## States

- `ok` - Pixels are ready and displaying
- `disabled` - Pixel display is disabled
- `error` - An initialization error occurred

## Example Settings

```json
{
    "pixel": {
        "enabled": true,
        "pixelpin": 18,
        "panel_width": 8,
        "panel_height": 8,
        "x_panels": 3,
        "y_panels": 2,
        "pixeltype": "RGB",
        "brightness": 1.0,
        "animation": "None"
    }
}
```

## Console Usage

```
pixel.on
pixel.fill 255 0 0
pixel.set_rgb 0 0 255 128 0
pixel.show_text 0 0 255 255 255 "Hello"
pixel.stop
```

## Code Usage

```python
# Get the pixel manager instance
pixel = clb.get_service_handle("pixel")

# Enable pixel display
pixel.command_enable()

# Fill with color
pixel.command_fill_display(255, 0, 0)

# Set individual pixel
pixel.command_set_pixel_rgb(0, 0, 255, 128, 0)

# Show text
pixel.command_show_text(0, 0, 255, 255, 255, "Hello")

# Stop animation
pixel.command_stop()
pixel.set_rgb 0 0 255 128 0
pixel.show_text 0 0 255 255 255 "Hello"
```

## Notes

- Total pixels = panel_width × panel_height × x_panels × y_panels
- The manager updates pixel display at approximately 30 FPS (33ms interval)
- Animations can be played alongside other display elements
- Text display supports color specification and scrolling

---

[↑ Back to README](../../README.md)
