# Tap Manager

Detects button presses on a single GPIO pin and publishes tap events. Recognises individual taps, double-taps, triple-taps, and idle (no-activity) conditions. Multiple instances can run under different names to handle multiple buttons.

## Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable this manager |
| `tap_pin` | int | — | **Required.** GPIO pin number to monitor |
| `name` | str | `"button"` | Event namespace; events are published as `tap.<name>.*` |
| `pullup` | bool | `true` | Enable internal pull-up resistor |
| `active_level` | int | `0` | Pin level that counts as a press (0 for pull-up buttons, 1 for pull-down) |
| `debounce_ms` | int | `20` | Debounce window in milliseconds |
| `max_intertap_ms` | int | `500` | Maximum gap between taps for them to be counted as one sequence |
| `end_gap_ms` | int | `500` | Gap of silence after the last tap before the sequence is published |
| `idle_ms` | int | `1000` | Inactivity duration before the idle event fires |

## Events

Event names use the configured `name` setting as a namespace:

| Event | Payload | Description |
|-------|---------|-------------|
| `tap.<name>.tap` | `name`, `count_so_far`, `pin`, `t_ms` | Fired on each individual press |
| `tap.<name>.sequence` | `name`, `count`, `pin`, `t_ms` | Fired once when the tap sequence ends; `count` is the total number of taps |
| `tap.<name>.double` | `name`, `count`, `pin`, `t_ms` | Convenience event for a two-tap sequence |
| `tap.<name>.triple` | `name`, `count`, `pin`, `t_ms` | Convenience event for a three-tap sequence |
| `tap.<name>.idle` | `name`, `idle_ms`, `idle_for_ms` | Fired when the pin has been inactive for `idle_ms` |

## Dependencies

None (reads the pin directly in the update loop).

## States

| State | Description |
|-------|-------------|
| `ok` | Running and monitoring the pin |
| `error` | `tap_pin` not set or pin configuration failed |
| `disabled` | Manager is disabled |

## Notes

- The `sequence` event is the most reliable way to react to multi-tap gestures. Subscribe to `double` or `triple` for convenience shortcuts.
- `end_gap_ms` controls the latency between the last tap and the sequence event. Lower values give faster response but may split fast double-taps into two singles.
- To monitor a second button, add a second manager entry in `settings.json` with a different `name` and `tap_pin`.

## Example Settings

```json
{
    "tap": {
        "enabled": true,
        "tap_pin": 14,
        "name": "mode_button",
        "pullup": true,
        "active_level": 0,
        "debounce_ms": 20,
        "max_intertap_ms": 400,
        "end_gap_ms": 450,
        "idle_ms": 5000
    }
}
```

## Example Usage

```
# Events published when button on GPIO 14 is tapped:
# tap.mode_button.tap       — on each press
# tap.mode_button.double    — after two quick presses
# tap.mode_button.sequence  — after any sequence completes
# tap.mode_button.idle      — after 5 seconds of no activity
```
