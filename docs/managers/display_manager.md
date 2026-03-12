[← Back to README](../../README.md)

# Display Manager

Manages LCD and e-ink displays for text and graphics output.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | true | Enable/disable display |
| `type` | string | "lcd" | Display type: "lcd" or "eink" |
| `font` | string | "bitmap8" | Font selection |
| `text_scale` | int | 2 | Text scale factor |

## Services (Commands)

Display manager provides graphics interface for text and display items.

## Events

This manager does not emit any events.

## Dependencies

This manager has no dependencies (but requires specific hardware).

## States

- `ok` - Display initialized and ready
- `error` - Display initialization failed
- `disabled` - Display is disabled

## Supported Hardware

### LCD Display
- Requires: `gfx_pack` library
- Display interface for Pimoroni GFX Pack

### E-Ink Display
- Requires: `picographics` library with DISPLAY_INKY_PACK
- Low-power e-ink display for persistent text

## Example Settings

```json
{
    "display": {
        "enabled": true,
        "type": "lcd",
        "font": "bitmap8",
        "text_scale": 2
    }
}
```

## Code Usage

```python
# Get the display manager instance
display = clb.get_service_handle("display")

# Clear display
display.hardware.clear()

# Write text
display.hardware.text("Hello", 0, 0, scale=2)

# Update display
display.hardware.update()

# Measure text width
width = display.hardware.measure_text("Hello", scale=2)
```

## Text Methods

- Clear display
- Write text at position (x, y)
- Measure text width for positioning
- Scale text output

## Display Types

| Type | Library | Power | Use Case |
|------|---------|-------|----------|
| lcd | gfx_pack | High | Real-time updates, animations |
| eink | picographics | Low | Static text, battery-powered devices |

## Notes

- Optional hardware - graceful degradation if libraries not available
- E-ink displays require full screen update (slower but low power)
- LCD displays can update portions of screen (faster updates)
- Text rendering depends on font and scale settings
- Coordinates are (0,0) at top-left

---

[↑ Back to README](../../README.md)
