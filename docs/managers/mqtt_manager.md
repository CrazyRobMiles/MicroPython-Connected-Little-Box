[← Back to README](../../README.md)

# MQTT Manager

Provides MQTT connectivity for remote message publishing/subscribing and file transfer capabilities.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | false | Enable/disable MQTT |
| `mqtthost` | string | "" | MQTT broker hostname or IP |
| `mqttport` | int | 1883 | MQTT broker port |
| `mqttuser` | string | "" | MQTT username (empty for no auth) |
| `mqttpwd` | string | "" | MQTT password |
| `mqttsecure` | string | "no" | "yes" for TLS, "no" for plain TCP |
| `devicename` | string | "CLB-{uid}" | Name of this device (used as client ID) |
| `topicbase` | string | "lb/data" | Base topic for published data |
| `filebase` | string | "lb/file" | Base topic for file transfer |

## Services (Commands)

| Service | Description |
|---------|-------------|
| `connect` | Connect to MQTT broker |
| `disconnect` | Disconnect from MQTT broker |
| `publish_status` | Publish current device status |
| `fetch_file <path> [target_path]` | Download a file from another device via MQTT |

## Events

| Event | Description |
|-------|-------------|
| `mqtt.connected` | Connected to MQTT broker |
| `mqtt.disconnected` | Disconnected from MQTT broker |
| `mqtt.message` | Raw MQTT message received |
| `file.request` | File range request received from another device |
| `file.range_sent` | File range successfully sent |
| `file.range_error` | Error occurred while serving file range |
| `file.fetch_started` | File download started |
| `file.fetch_range` | Received a range of file data |
| `file.fetch_complete` | File download completed successfully |
| `file.fetch_error` | Error occurred during file download |

## Dependencies

- `wifi` - WiFi must be enabled and connected

## States

- `waiting` - Waiting for WiFi to become available
- `connecting` - Connecting to MQTT broker
- `ok` - Connected and ready
- `error` - Connection error
- `disabled` - MQTT is disabled

## Example Settings

```json
{
    "mqtt": {
        "enabled": true,
        "mqtthost": "192.168.1.100",
        "mqttport": 1883,
        "mqttuser": "user",
        "mqttpwd": "password",
        "mqttsecure": "no",
        "devicename": "CLB-MyDevice",
        "topicbase": "lb/data",
        "filebase": "lb/file"
    }
}
```

## Console Usage

```
mqtt.connect
mqtt.disconnect
mqtt.publish_status
mqtt.fetch_file /settings.json /settings_backup.json
```

## Code Usage

```python
# Get the MQTT manager instance
mqtt = clb.get_service_handle("mqtt")

# Connect/disconnect
mqtt.connect()
mqtt.disconnect()

# Subscribe to MQTT events
event = clb.get_event("mqtt.connected")
if event:
    event.subscribe(on_mqtt_connected)

# Handler for MQTT connection
def on_mqtt_connected(event_data):
    print("MQTT connected!")

# Fetch a file
mqtt.fetch_file("/settings.json", "/settings_backup.json")
mqtt.publish_status
mqtt.fetch_file /settings.json /settings_backup.json
```

## Notes

- MQTT provides a publish/subscribe messaging protocol for IoT devices
- File transfer uses base64 encoding for binary safety
- Files are transferred in chunks with configurable range sizes (default 2000 bytes)
- Any device on the MQTT network can request files from this device
- The Updater manager uses MQTT for firmware updates

---

[↑ Back to README](../../README.md)
