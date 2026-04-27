[← Back to README](../../README.md)

# Clock Manager

Synchronizes the device time with an NTP (Network Time Protocol) server and provides time-based events.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | false | Enable/disable the clock |
| `ntpserver` | string | "129.6.15.28" | NTP server address (numeric IP recommended) |
| `tz_offset_minutes` | int | 0 | Timezone offset in minutes (e.g., -300 for UTC-5, 60 for UTC+1) |
| `resync_minutes` | int | 180 | Interval in minutes between time resynchronisation |
| `sync_timeout_ms` | int | 2000 | NTP request timeout in milliseconds |
| `sync_on_start` | bool | true | Synchronise time on startup |
| `dst_uk_enabled` | bool | true | Apply UK/BST daylight saving time automatically |
| `dst_uk_delta_minutes` | int | 60 | Extra minutes added during BST (UK DST) |

## Services (Commands)

| Service | Description |
|---------|-------------|
| `on` | Enable the clock manager |
| `off` | Disable the clock manager |
| `sync` | Force an immediate async NTP sync (requires WiFi) |
| `time` | Return current local time as `(hour, minute, second)` |
| `date` | Return current local date as `(year, month, day)` |
| `dst_test [year]` | Run a deterministic UK DST transition test for the given year |

## Events

| Event | Description |
|-------|-------------|
| `clock.second` | Fired every second |
| `clock.minute` | Fired when the minute changes |
| `clock.hour` | Fired when the hour changes |
| `clock.day` | Fired when the day changes |

## Dependencies

- `wifi` - WiFi must be enabled and connected for NTP synchronization

## States

- `waiting` - Waiting for WiFi to become available
- `syncing` - Currently synchronizing time with NTP server
- `ok` - Time is synchronized and valid
- `error` - A synchronization error occurred
- `disabled` - Clock manager is disabled

## Example Settings

```json
{
    "clock": {
        "enabled": true,
        "ntpserver": "129.6.15.28",
        "tz_offset_minutes": -300,
        "resync_minutes": 180,
        "sync_on_start": true
    }
}
```

## Code Usage

```python
# Get the clock manager instance
clock = clb.get_service_handle("clock")

# Get current time
current_time = clock._now_epoch_local()

# Subscribe to time events
event = clb.get_event("clock.minute")
if event:
    event.subscribe(my_minute_handler)

# Handler function
def my_minute_handler(event_data):
    print("Minute changed!")
```

## Notes

- The clock uses NTP for accurate time synchronization
- Time is stored in the Pico's RTC (Real-Time Clock)
- Time resynchronization happens periodically to account for clock drift
- Other managers can subscribe to clock events to trigger time-based actions

---

[↑ Back to README](../../README.md)
