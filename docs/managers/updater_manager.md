[← Back to README](../../README.md)

# Updater Manager

Manages firmware updates by fetching manifests and updating files via MQTT.

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | bool | true | Enable/disable update checking |
| `manifest_url` | string | GitHub raw URL | URL to fetch manifest from |
| `check_interval_minutes` | int | 120 | Interval between update checks |
| `source` | string | "" | Device name for peer updates (empty = server) |
| `auto_restart` | bool | true | Automatically restart after successful update |

## Services (Commands)

| Service | Description |
|---------|-------------|
| `check` | Check for updates without installing |
| `check_verbose` | Check with detailed logging |
| `update` | Check for and install updates |
| `update_verbose` | Update with detailed logging |

## Events

| Event | Description |
|-------|-------------|
| `check.start` | Update check started |
| `check.complete` | Update check completed (no updates) |
| `check.error` | Update check failed |
| `update.start` | Update process started |
| `update.file_start` | Starting to update a file |
| `update.file_done` | Completed updating a file |
| `update.complete` | Update process completed successfully |
| `update.error` | Update process failed |

## Dependencies

- `mqtt` - MQTT must be available for file downloads

## States

- `ok` - Updater ready
- `checking` - Checking for updates
- `downloading` - Downloading update files
- `error` - Update error occurred
- `disabled` - Updater is disabled

## Example Settings

```json
{
    "updater": {
        "enabled": true,
        "manifest_url": "https://raw.githubusercontent.com/CrazyRobMiles/MicroPython-Connected-Little-Box/main/manifest.json",
        "check_interval_minutes": 120,
        "source": "",
        "auto_restart": true
    }
}
```

## Console Usage

```
updater.check
updater.check_verbose
updater.update
updater.update_verbose
```

## Code Usage

```python
# Get the updater manager instance
updater = clb.get_service_handle("updater")

# Check for updates
updater.command_check()

# Update with verbose output
updater.command_update_verbose()

# Subscribe to update events
event = clb.get_event("update.complete")
if event:
    event.subscribe(on_update_complete)

def on_update_complete(event_data):
    print("Update completed!")
```

## Manifest Format

The manifest JSON file contains version information for all files:

```json
{
    "version": "1.0.2",
    "files": {
        "main.py": "1.0.2",
        "clb.py": "1.0.3",
        "managers/blink_manager.py": "1.0.2"
    }
}
```

## Update Process

1. Fetch manifest from configured source
2. Generate local manifest from file headers
3. Compare versions to find outdated files
4. Download each outdated file via MQTT
5. Verify file integrity
6. Rename temporary files to final locations
7. Optionally restart device

## Notes

- Updates are downloaded with `.new` extension and verified before replacing
- The updater generates a local manifest (`manifest_local.json`) for comparison
- Files are transferred in chunks (default 2000 bytes per MQTT message)
- Safe atomic rename ensures no corrupted states
- Supports both server-based and peer-to-peer device updates

---

[↑ Back to README](../../README.md)
