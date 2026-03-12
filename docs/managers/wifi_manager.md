[← Back to README](../../README.md)

# WiFi Manager

Manages WiFi connectivity for the device. Many other managers depend on WiFi.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | false | Enable/disable WiFi |
| `wifissid1` | string | "" | WiFi network SSID |
| `wifipwd1` | string | "" | WiFi network password |

## Services (Commands)

| Service | Description |
|---------|-------------|
| `on` | Enable WiFi and connect |
| `off` | Disable WiFi and disconnect |

## Events

This manager does not emit any events. However, its state is monitored by dependent managers.

## Dependencies

This manager has no dependencies.

## States

- `not connected` - WiFi is not currently connected
- `connecting` - WiFi connection is in progress
- `ok` - WiFi is successfully connected and ready
- `error` - A WiFi error occurred
- `disabled` - WiFi is disabled

## Example Settings

```json
{
    "wifi": {
        "enabled": true,
        "wifissid1": "MyNetwork",
        "wifipwd1": "MyPassword"
    }
}
```

## Console Usage

```
wifi.on
wifi.off
```

## Code Usage

```python
# Get the WiFi manager instance
wifi = clb.get_service_handle("wifi")

# Enable WiFi
wifi.command_enable_wifi()

# Disable WiFi
wifi.command_disable_wifi()

# Check WiFi state
wifi.on
wifi.off
```

## Notes

- WiFi must be enabled before any manager that depends on it (like MQTT or Clock) can function
- Connection timeout is 10 seconds
- Power saving is disabled to ensure responsive communication

---

[↑ Back to README](../../README.md)
