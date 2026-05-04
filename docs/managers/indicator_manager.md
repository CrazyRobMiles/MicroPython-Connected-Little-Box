[← Back to README](../../README.md)

# Indicator Manager

Controls a small number of individually-addressed NeoPixel (WS2812B) LEDs. Designed for status indicators, activity lights, and simple decorative effects where you want to set, fade, or animate individual pixels without the panel/grid complexity of the Pixel Manager.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | true | Enable/disable the manager |
| `pixelpin` | int | 18 | GPIO pin for pixel data |
| `count` | int | 8 | Number of pixels in the strip |
| `pixeltype` | string | "RGB" | Pixel colour format (`"RGB"` or `"GRB"`) |
| `brightness` | float | 1.0 | Brightness multiplier (0.0–1.0) |
| `fade_steps` | int | 20 | Number of update steps (~33ms each) for fade transitions (~660ms at default) |

## Services (Commands)

| Service | Description |
|---------|-------------|
| `set(index, r, g, b)` | Set a pixel to a colour immediately |
| `fade(index, r, g, b)` | Fade a pixel to a colour over `fade_steps` |
| `fill(r, g, b)` | Set all pixels to a colour immediately |
| `fade_all(r, g, b)` | Fade all pixels to a colour |
| `sequence(index, [[r,g,b],...], rate=10)` | Cycle a pixel through a list of colours |
| `sequence_all([[r,g,b],...], rate=10)` | Cycle all pixels through the same colour list |
| `stop(index)` | Stop the colour sequence on one pixel |
| `stop_all()` | Stop all running colour sequences |
| `off()` | Turn all pixels off immediately |
| `brightness(b)` | Set brightness multiplier (0.0–1.0) |
| `test()` | Light all pixels in a rainbow pattern |

### Sequence timing

Each colour in a sequence is displayed in two phases:

1. **Fade** — the pixel transitions from its current colour to the next over `fade_steps` update ticks (~33ms each).
2. **Dwell** — the pixel holds at the target colour for `rate` ticks before moving on.

Total time per colour ≈ `(fade_steps + rate) × 33ms`.

With the default `fade_steps` of 20, a `rate` of 10 gives roughly 1 second per colour. Different pixels can run at different rates simultaneously.

## Events

This manager does not emit any events.

## Dependencies

This manager has no dependencies.

## States

- `ok` — Pixels are ready
- `disabled` — Manager is disabled by config
- `error` — An initialisation error occurred

## Example Settings

```json
{
    "indicator": {
        "enabled": true,
        "pixelpin": 18,
        "count": 4,
        "pixeltype": "RGB",
        "brightness": 0.8,
        "fade_steps": 20
    }
}
```

## Console Usage

```
# Set and fade individual pixels
indicator.set(0, 255, 0, 0)
indicator.fade(1, 0, 255, 0)

# Fill all pixels
indicator.fill(0, 0, 100)
indicator.fade_all(0, 0, 0)

# Cycle pixel 0 slowly through red → green → blue
indicator.sequence(0, [[255,0,0],[0,255,0],[0,0,255]], 30)

# Cycle pixel 1 through the same colours three times faster
indicator.sequence(1, [[255,0,0],[0,255,0],[0,0,255]], 10)

# Run different sequences on different pixels at different rates
indicator.sequence(0, [[255,0,0],[255,100,0]], 5)
indicator.sequence(1, [[0,255,0],[0,0,255],[255,0,255]], 20)

# Stop sequences
indicator.stop(0)
indicator.stop_all()

indicator.off()
indicator.brightness(0.5)
```

## Code Usage

```python
ind = clb.get_service_handle("indicator")
ind.cmd_set(0, 255, 0, 0)
ind.cmd_sequence(0, [[255,0,0],[0,255,0],[0,0,255]], 15)
ind.cmd_stop_all()
ind.cmd_off()
```

## Notes

- Pixels are addressed by index starting at 0.
- Calling `set`, `fade`, `fill`, or `fade_all` on a pixel cancels any running sequence on it.
- `rate` controls dwell time only; transition speed is always governed by the `fade_steps` setting.
- For `GRB` strips the colour byte order is swapped automatically — always pass colours as `r, g, b`.
- Compared to the [Pixel Manager](pixel_manager.md), this manager uses a simple linear index rather than x/y panel coordinates, and has no animation engine, text rendering, or clock display.

---

[↑ Back to README](../../README.md)
