[← Back to README](../../README.md)

# SX-70R Manager

Controls SX-70 format cameras (via BLE) for remote camera operations and exposure control.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | true | Enable/disable camera control |
| `auto_connect` | bool | true | Automatically connect to camera on startup |
| `scan_ms` | int | 6000 | BLE scan timeout in milliseconds |
| `preferred_addr` | string | "" | Preferred camera MAC address |
| `require_approval` | bool | true | Require approval for new camera addresses |
| `approved_addrs` | array | [] | List of pre-approved MAC addresses |
| `reconnect_backoff_ms` | int | 2000 | Backoff time between reconnection attempts |
| `debug` | bool | true | Enable debug logging |

## Services (Commands)

| Service | Description |
|---------|-------------|
| `connect` | Scan and connect to camera |
| `disconnect` | Disconnect from camera |
| `scan_register` | Scan for new cameras and display addresses |
| `approved` | List approved camera addresses |
| `set_preferred <AA:BB:CC:DD:EE:FF>` | Set preferred camera address |
| `request_iso` | Request current ISO setting from camera |
| `get_iso` | Get last received ISO value |
| `fire_shutter <exp_hex> [timer_s] [hold_ms]` | Fire camera shutter |

## Events

| Event | Description |
|-------|-------------|
| `camera.connected` | Camera connected successfully |
| `camera.disconnected` | Camera disconnected |
| `camera.iso` | ISO value received from camera |
| `camera.exposure_started` | Shutter exposure started |
| `camera.exposure_finished` | Shutter exposure finished |
| `camera.error` | Camera error occurred |

## Dependencies

This manager has no dependencies.

## States

- `ok` - Camera connected and ready
- `idle` - Camera idle, not connected
- `connecting` - Connecting to camera via BLE
- `error` - Connection or communication error
- `disabled` - Camera manager is disabled

## Camera Connection

Cameras are identified by BLE advertisement name "CH9141BLE2U". The manager can:

1. **Scan**: Find available cameras
2. **Auto-connect**: Connect to preferred camera
3. **Approval workflow**: Require user approval for new addresses
4. **Multi-device**: Support multiple cameras with address whitelisting

## Example Settings

```json
{
    "sx70r": {
        "enabled": true,
        "auto_connect": true,
        "scan_ms": 6000,
        "preferred_addr": "54:14:A7:66:31:CD",
        "require_approval": true,
        "approved_addrs": [
            "54:14:A7:66:31:CD",
            "54:14:A7:66:31:CE"
        ],
        "reconnect_backoff_ms": 2000,
        "debug": true
    }
}
```

## Console Usage

```
sx70r.connect
sx70r.disconnect
sx70r.scan_register
sx70r.request_iso
sx70r.fire_shutter 0x01
sx70r.fire_shutter 0x01 2 500
```

## Code Usage

```python
# Get the camera manager instance
camera = clb.get_service_handle("sx70r")

# Connect to camera
camera.command_connect()

# Disconnect from camera
camera.command_disconnect()

# Request ISO
camera.command_request_iso()

# Fire shutter
camera.command_fire_shutter("0x01")

# Subscribe to camera events
event = clb.get_event("camera.connected")
if event:
    event.subscribe(on_camera_connected)

sx70r.fire_shutter 0x01
sx70r.fire_shutter 0x01 2 500
```

## Shutter Control

The `fire_shutter` command accepts:
- `exp_hex`: Exposure mode as hex (0x01, 0x02, etc.)
- Optional `self_timer_s`: Self-timer delay in seconds
- Optional `hold_ms`: How long to hold shutter open in milliseconds

## BLE Protocol

- Characteristic `FFF0`: Service UUID
- Characteristic `FFF1`: Notify/Read (receive data)
- Characteristic `FFF2`: Write (send commands)
- CCCD `2902`: Client characteristic descriptor for notifications

## Notes

- BLE scanning timeout prevents long hangs
- Reconnection attempts use exponential backoff
- ISO (film speed) can be queried and adjusted via commands
- Exposure control supports both auto and manual modes
- Address approval prevents accidental connection to wrong devices

---

[↑ Back to README](../../README.md)
