# Connected Little Box – Settings Management
### How Settings Are Loaded, Stored, Updated, Notified, and Used

The Connected Little Box (CLB) framework implements a flexible and extensible settings system used by every manager. Settings are defined by managers, merged with persisted values, exposed in the console, and stored in `settings.json`. Managers can also be notified when a setting changes.

This document describes the **current behaviour** of the settings subsystem, including:

- The `device_default_settings` and `app_default_settings` class attribute patterns  
- App-level settings templates and the `select-app` command  
- Dotted-path and indexed-path setting updates  
- Automatic persistence via DeviceConfigurator  
- Manager notifications via `on_setting_changed()`  
- Load-time enable/disable logic  
- Nested settings structures  
- Console update rules  

---

# 📜 Overview

Each CLB **manager**:

- Declares its own default settings via a `device_default_settings` (device managers) or `app_default_settings` (app managers) class attribute  
- Receives persisted settings merged with its defaults at startup  
- Can be enabled/disabled via its `"enabled"` flag  
- May define nested structures (lists or dictionaries)  
- Is able to react dynamically to live setting changes  
- Persists runtime changes to disk via the Configurator  

Settings are stored per-manager under its name in the central `settings.json` file.

---

# 🗂️ 1. Settings File Format (`settings.json`)

Settings are stored as:

```json
{
    "wifi": {
        "enabled": true,
        "wifissid1": "MyNetwork",
        "wifipwd1": "secret"
    },
    "stepper": {
        "enabled": false,
        "motors": [
            { "pins": [2,3,4,5], "wheel_diameter_mm": 69.0 },
            { "pins": [6,7,8,9], "wheel_diameter_mm": 69.0 }
        ]
    }
}
```

Each manager owns **only its own subtree**.

---

# 2. Declaring Default Settings

Device managers inherit from `CLBDeviceManager` and declare a flat `device_default_settings` **class attribute**:

```python
from managers.base_manager import CLBDeviceManager

class Manager(CLBDeviceManager):
    device_default_settings = {
        "enabled": True,
        "panel_width": 8,
        "panel_height": 8,
    }

    def __init__(self, clb):
        super().__init__(clb)
```

`CLBDeviceManager.get_defaults()` reads `device_default_settings` automatically. For device managers the dict is flat (one level). Defaults:

- Provide safe initial values  
- Fill in any missing keys during a firmware upgrade  
- Are merged with persisted settings at startup  

---

# 3. App Managers and Full-Config Templates

`App_` managers configure a whole device for a specific application. They inherit from `CLBAppManager` and declare `app_default_settings` — a **complete `settings.json` template** with every manager section the application needs:

```python
from managers.base_manager import CLBAppManager

class Manager(CLBAppManager):
    file = "App_lamp"
    app_default_settings = {
        "pixel": {
            "enabled": True,
            "pixelpin": 18,
            "panel_width": 8,
            "panel_height": 8,
            ...
        },
        "rotary_encoder": {
            "enabled": True,
            "encoders": [
                {"name": "color",      "clk_pin": 16, "dt_pin": 17, "btn_pin": -1},
                {"name": "brightness", "clk_pin": 19, "dt_pin": 20, "btn_pin": -1}
            ]
        },
        "App_lamp": {
            "enabled": True,
            "default_red": 255,
            "dependencies": ["pixel", "rotary_encoder"],
            ...
        }
    }
```

The App_ manager’s own per-instance defaults are taken from the sub-dict whose key matches the manager’s module name (e.g. `"App_lamp"`). All other sections are written verbatim to `settings.json` when the app is selected.

## Selecting an Application

The REPL command:

```
select-app
```

lists all registered applications (from `app_manifest.py`), lets the user choose one by number, writes that app’s `app_default_settings` as the entire `settings.json`, and resets the device. On the next boot every manager listed in the template is loaded automatically.

This allows a single firmware image to support multiple hardware configurations — just run `select-app` to switch between them without touching any files manually.

---

# 4. Startup Settings Merge

During startup (`clb.setup()`):

1. The CLB iterates through the entries in `settings.json`  
2. For each entry that has `"enabled": true`, it attempts to load the corresponding manager module  
3. It calls `manager.get_defaults()`, which reads `device_default_settings` or `app_default_settings` depending on the manager type  
4. Any key present in the defaults but absent from the stored settings is inserted  

Result:

- Persisted values override defaults  
- All missing fields receive defaults from `default_settings`  
- Managers always see a complete `self.settings` structure  

---

# 5. Manager Enable/Disable Behaviour

The `"enabled"` setting does more than control behaviour — it decides whether a manager even **exists**.

If a manager's setting contains:

```json
{ "enabled": false }
```

Then:

- The manager is **not imported**
- No instance is created
- It receives **no updates**
- It cannot receive setting change notifications

This behaviour prevents loading hardware-dependent managers that would otherwise crash on setup.

---

# 6. Nested Settings and Dotted-Path Access

Settings may be arbitrarily nested:

- `wifi.ssid`
- `pixel.panel_width`
- `stepper.motors[0].wheel_diameter_mm`
- `stepper.motors[1].pins[2]`

The CLB `set` command now uses **dotted-path syntax**:

```
set stepper.motors[0].wheel_diameter_mm=69.1
```

The path parser supports:

- Dictionary keys  
- List indexing via `[index]`  
- Mixed structures  
- Arbitrary depth  

Invalid paths (e.g., accessing list elements using dotted syntax) correctly generate error messages.

---

# 7. Changing Settings at Runtime

Settings may be changed dynamically using:

```
set <manager>.<path>=<value>
```

Examples:

```
set pixel.panel_width=16
set wifi.wifissid1="NewNetwork"
set stepper.motors[0].wheel_diameter_mm=70.2
set stepper.motors[1].pins[2]=15
```

The value is type-coerced according to the original data:

- Ints stay ints  
- Floats stay floats  
- Boolean text becomes bool  
- JSON becomes native structures  
- Strings remain strings unless automatically coerced  

After a change:

1. The setting is written into memory  
2. The configuration file is saved immediately  
3. If the manager is enabled, it receives:

```python
on_setting_changed(path, old_value, new_value)
```

---

# 8. Manager Notification: `on_setting_changed()`

A manager may define:

```python
def on_setting_changed(self, path, old, new):
    print("Setting changed:", path, old, "→", new)
```

This allows:

- Reconfiguration of hardware  
- Rebuilding lookup tables  
- Updating cached derived settings  
- Triggering recalculations  

Notifications include:

- `path`: dotted path string (`"motors[0].wheel_diameter_mm"`)
- `old`: previous value  
- `new`: updated value  

Managers **only** receive this callback if:

- They are currently enabled  
- They were instantiated at boot  
- The setting belongs to them  
- The path resolves correctly  

---

# 9. Persistent Saving of Settings

After each successful `set` command:

```python
self.config.save()
```

writes the full updated settings tree back to `/settings.json`.

This ensures:

- Power-cycle-safe configuration  
- Manager defaults are not lost  
- Remote-control via MQTT or USB terminal persists changes  

---

# 10. Resetting Settings to Defaults

The built-in command:

```
reset
```

Overwrites the file with the defaults from `device_default_settings` or `app_default_settings` **for all loaded managers**.

Managers that are disabled do not appear in the reset output.

---

# 11. Writing a New Manager

**Device managers** inherit from `CLBDeviceManager` and use a flat `device_default_settings`:

```python
from managers.base_manager import CLBDeviceManager

class Manager(CLBDeviceManager):
    version = "1.0.0"

    device_default_settings = {
        "my_pin": 10,
        "my_rate": 9600,
    }

    def __init__(self, clb):
        super().__init__(clb)

    def setup(self, settings):
        super().setup(settings) # merges device_default_settings into settings
        if not self.enabled:
            return
        # self.settings is now fully populated
        pin = self.settings["my_pin"]
```

**App managers** inherit from `CLBAppManager` and use `app_default_settings` — a complete `settings.json` template. Give the manager a `file` attribute matching the key in `app_manifest.py`:

```python
from managers.base_manager import CLBAppManager

class Manager(CLBAppManager):
    file = "App_my_app"
    app_default_settings = {
        "gpio": { "enabled": True, "input_pins": [...], ... },
        "App_my_app": {
            "enabled": True,
            "dependencies": ["gpio"],
            ...
        }
    }
```

---

# 12. Summary

| Stage | Description |
|-------|-------------|
| **Defaults** | Device managers declare `device_default_settings`; App managers declare `app_default_settings` |
| **App template** | App_ managers include a full multi-manager `app_default_settings` |
| **select-app** | Writes an app's `app_default_settings` as `settings.json` and resets |
| **Load** | CLB loads `settings.json` and merges with the manager's defaults |
| **Enable/Disable** | `"enabled": false` prevents the manager from being instantiated |
| **Setup** | Manager receives its final merged settings during `setup()` |
| **Runtime Updates** | Users update values using dotted paths |
| **Notification** | `on_setting_changed()` is called for live updates |
| **Persistence** | The DeviceConfigurator saves updates immediately |
| **Nested Support** | Arbitrary nesting and list indices are supported |

The CLB settings system is:

- Consistent — device managers use `device_default_settings`, app managers use `app_default_settings`  
- Extensible — add a key to the defaults and it is automatically available  
- App-aware — `select-app` can reconfigure an entire device from a single `app_default_settings` attribute  
- Safe across updates — missing keys are always filled in from defaults  
- Friendly to both console and remote MQTT configuration  

