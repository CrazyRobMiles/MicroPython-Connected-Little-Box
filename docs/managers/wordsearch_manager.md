[← Back to README](../../README.md)

# WordSearch Clock Manager

A full word-search-style clock and alarm application. Displays the current time as highlighted words on a pixel LED grid (e.g. "IT IS HALF PAST TEN"), with an alarm that plays audio tracks via the DFPlayer Manager. Four GPIO buttons allow the user to set the alarm time and adjust display brightness.

The word positions are loaded from a JSON layout file (e.g. `Clock.json`) that maps each word to its position on the pixel grid.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | false | Enable/disable the wordsearch clock |
| `wordsearch_file` | string | "Clock.json" | JSON file containing the word-search layout |
| `wordsearch_letter_delay_ms` | int | 250 | Delay between illuminating individual letters when spelling out a word |
| `wordsearch_word_delay_ms` | int | 1000 | Delay between words during the reveal animation |
| `wordsearch_display_gap_ms` | int | 5000 | How long to hold the completed time display before refreshing |
| `run_on_power_up` | bool | true | Start the clock display automatically on boot |
| `alarm_timeout_ms` | int | 30000 | How long the alarm sounds before automatically silencing (milliseconds) |
| `alarm_sample_interval_ms` | int | 1000 | Gap between alarm audio samples |
| `key_repeat_delay_ms` | int | 500 | Time before a held button starts repeating |
| `key_repeat_interval_ms` | int | 333 | Repeat rate while a button is held |
| `start_audio_track_no` | int | 3 | First alarm sound track number on the MicroSD card |
| `end_audio_track_no` | int | 20 | Last alarm sound track number (inclusive); tracks are chosen at random |

## Services (Commands)

This manager provides no console commands.

## Events

This manager subscribes to but does not publish its own events.

## Dependencies

- `pixel` — LED pixel display for the word-search grid
- `clock` — Time source; subscribes to `clock.minute` to update the display
- `dfplayer` — Audio playback for alarm sounds (optional — alarm will still trigger without audio)
- `gpio` — Six input pins must be configured with these names:

| GPIO name | Purpose |
|-----------|---------|
| `hour_button` | Increment alarm hour |
| `min_button` | Increment alarm minute |
| `up_button` | Increase brightness |
| `down_button` | Decrease brightness |
| `player_status` | DFPlayer busy/done signal |

## States

| State | Description |
|-------|-------------|
| `inactive` | Manager loaded but display not yet started |
| `showing words` | Revealing the current time word by word |
| `animating words` | Words are being animated |
| `showing time` | Time words are fully displayed and held |
| `error` | Layout file not found or failed to load |
| `disabled` | Manager is disabled |

## Notes

- The word layout is defined in `Clock.json` (or another file set via `wordsearch_file`). Each entry maps a word string to pixel coordinates on the grid.
- Alarm settings (time, enabled state) are persisted to a separate settings store on the device so they survive reboots.
- Alarm audio tracks are played in random order between `start_audio_track_no` and `end_audio_track_no`. Track 1 is the "alarm off" message and track 2 is the "alarm on" message — these are played when the user toggles the alarm via the hour/minute buttons.
- See [Alarm Sounds README](../../resources/wordsearch%20clock/sounds/README.md) for instructions on preparing the MicroSD card.

## Example Settings

```json
{
    "pixel": {
        "enabled": true,
        "pixelpin": 18,
        "panel_width": 16,
        "panel_height": 16,
        "x_panels": 1,
        "y_panels": 1,
        "pixeltype": "GRB"
    },
    "clock": { "enabled": true },
    "dfplayer": {
        "enabled": true,
        "uart_id": 1,
        "tx_pin": 5,
        "rx_pin": 4,
        "volume": 20
    },
    "gpio": {
        "enabled": true,
        "input_pins": [
            { "name": "hour_button",   "pin": 10, "pullup": true },
            { "name": "min_button",    "pin": 11, "pullup": true },
            { "name": "up_button",     "pin": 12, "pullup": true },
            { "name": "down_button",   "pin": 13, "pullup": true },
            { "name": "player_status", "pin": 14 }
        ]
    },
    "App_wordsearch_alarmclock": {
        "enabled": true,
        "wordsearch_file": "Clock.json",
        "wordsearch_letter_delay_ms": 250,
        "wordsearch_word_delay_ms": 1000,
        "wordsearch_display_gap_ms": 5000,
        "alarm_timeout_ms": 30000,
        "start_audio_track_no": 3,
        "end_audio_track_no": 54
    }
}
```

---

[↑ Back to README](../../README.md)
