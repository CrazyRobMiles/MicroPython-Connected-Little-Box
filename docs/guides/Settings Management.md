# 🧩 Connected Little Box – Settings Management  
### How Settings Are Loaded, Stored, Updated, and Used

The Connected Little Box (CLB) framework provides a unified mechanism for storing configuration values for each manager, loading them on startup, and updating them dynamically during runtime.  
This document explains the full lifecycle of settings, from defaults to persistent storage.

---

# 📜 Overview

Each **manager** in CLB:

- Defines **default settings**
- Receives **stored settings** from persistent storage
- Applies and merges these settings during `setup()`
- Exposes settings through the CLB console command system  
- May request **saving** of settings to `/settings.json`
- Can safely detect if it is **enabled** or **disabled** via settings

This system is central to the configuration of:

- Network setup  
- Pixel panel configuration  
- Stepper/servo behaviour  
- Display modes  
- Script manager behaviour  
- Wordsearch/Clock configuration  
- And user-defined managers  

---

# 🗂️ Settings File Format

Settings are stored in:

```
/settings.json
```

This file contains a **top-level dictionary**, where each key is a manager name:

```json
{
    "wifi": {
        "enabled": true,
        "ssid": "MyNetwork",
        "password": "secret"
    },
    "mqtt": {
        "enabled": false,
        "mqtthost": "",
        "mqttport": 1883
    },
    "pixel": {
        "enabled": true,
        "panel_width": 8,
        "panel_height": 8
    }
}
```

Each manager controls **only its own section**.

---

# 📥 1. How Managers Declare Default Settings

Every manager calls the `CLBManager` constructor with a `defaults` dictionary:

```python
class Manager(CLBManager):
    def __init__(self, clb):
        super().__init__(clb, defaults={
            "enabled": True,
            "pin": "LED",
            "delay_seconds": 1.0
        })
```

The base class ensures:

- Every manager **always has** an `"enabled"` flag  
- Other defaults fill in missing values  
- Users can override these defaults in `settings.json`

Default settings are stored internally until merged.

---

# 🔀 2. How Settings Are Loaded on Startup

During system startup:

1. CLB scans `/managers`  
2. Creates **one manager instance** per file  
3. Loads `/settings.json`  
4. For each manager:

```python
merged = defaults.copy()
merged.update(stored_settings)
```

This means:

### ✔ Stored settings *override* defaults  
### ✔ Defaults fill in any missing values  
### ✔ New defaults automatically appear after an update  

The merged result is placed in:

```
manager.settings
```

---

# ⚙️ 3. How a Manager Receives Its Settings

In each manager, `setup()` is passed its merged settings dictionary:

```python
def setup(self, settings):
    super().setup(settings)

    if not self.enabled:
        self.state = self.STATE_DISABLED
        return

    pin = settings["pin"]
    delay = settings["delay_seconds"]
```

The base `setup()` performs:

- Merge of defaults with stored settings  
- Creation of `self.settings`  
- Creation of `self.enabled`  
- Setting initial manager state to “connecting” or “disabled”

A manager should *not* modify global settings inside `setup()`—only read them.

---

# 🔁 4. Changing Settings at Runtime

Users can change settings through the CLB console:

```
set pixel_panel_width=16
set wifi_enabled=false
```

The format is:

```
set <manager>_<setting>=<value>
```

CLB performs:

1. Parse manager name  
2. Parse setting name  
3. Coerce the value to the correct type  
4. Update `self.settings`  
5. Print confirmation

Example:

```
pixel.panel_width updated to 16 (int)
```

This **does not automatically save to disk** — the user must call:

```
save
```

(if you add a save command) or rely on the DeviceConfigurator.

---

# 💾 5. Persistent Saving of Settings

Settings persistence is handled by:

### ✔ `device_configurator.py`  
### ✔ Saving `/settings.json` in JSON format  
### (Optional) Obfuscated storage using XOR and a device-unique seed

Managers **never write settings themselves**.  
Instead, CLB or external tools call:

```python
configurator.save()
```

The DeviceConfigurator writes:

```json
{
    "pixel": {...},
    "wifi": {...},
    "wordsearch": {...},
    ...
}
```

This ensures consistency across reboots.

---

# 🔐 6. Safe Mode (SAFE_PIN)

The DeviceConfigurator can enforce “setup mode” if:

- The settings file is missing  
- The safe pin is pulled low  
- Loading settings fails  
- Obfuscation headers do not match  

In this mode, the device waits on USB for new settings to be sent.

This is primarily used for first-time configuration.

---

# 🚀 7. When Settings Affect Manager Startup

Every manager should:

1. Check `self.enabled` in `setup()`  
2. Set appropriate internal states  
3. Reflect failures by setting `self.state = STATE_ERROR`  
4. Set `self.state = STATE_OK` only when successfully configured  

This allows dependency-based managers (e.g., MQTT depends on WiFi) to wait until prerequisite managers are ready.

---

# 🔧 8. Example: Pixel Manager Settings Flow

### Defined defaults:

```python
{
    "pixelpin": 0,
    "panel_width": 8,
    "panel_height": 8,
    "x_panels": 3,
    "y_panels": 2,
    "brightness": 1.0
}
```

### Stored settings:

```json
{
    "panel_width": 16,
    "x_panels": 2
}
```

### Final merged settings:

```json
{
    "enabled": true,
    "pixelpin": 0,
    "panel_width": 16,
    "panel_height": 8,
    "x_panels": 2,
    "y_panels": 2,
    "brightness": 1.0
}
```

The manager then configures the NeoPixel panel accordingly.

---

# 🧪 9. Resetting Settings to Defaults

CLB provides a built-in command:

```
reset
```

This rewrites the settings file with:

```python
mgr.get_defaults()
```

For every manager.

This is useful when settings have become corrupted or incompatible.

---

# 🧭 10. Summary

| Stage | Description |
|-------|-------------|
| **Defaults** | Each manager declares safe starting values |
| **Load** | CLB loads `/settings.json` and merges with defaults |
| **Setup** | Managers receive configured settings in `setup()` |
| **Runtime Updates** | Users change settings using the `set` command |
| **Persistence** | Settings saved via DeviceConfigurator |
| **Safe Mode** | Ensures device recoverability |
| **Dependency-aware** | Managers set `STATE_OK` when fully configured |

This system allows CLB devices to be:

- Self-configuring  
- Robust across firmware updates  
- Easy to debug  
- Easy to remotely manage  
- Modular and extensible  

---

If you'd like a **PDF version**, **Quick Start card**, or **screenshots edition**, just ask!
