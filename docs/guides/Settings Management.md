# 🧩 Connected Little Box – Settings Management
### How Settings Are Loaded, Stored, Updated, Notified, and Used

The Connected Little Box (CLB) framework implements a flexible and extensible settings system used by every manager. Settings are defined by managers, merged with persisted values, exposed in the console, and stored in `settings.json`. Managers can also be notified when a setting changes.

This document describes the **current behaviour** of the settings subsystem, including:

- Dotted-path and indexed-path setting updates  
- Automatic persistence via DeviceConfigurator  
- Manager notifications via `on_setting_changed()`  
- Load-time enable/disable logic  
- Nested settings structures  
- Console update rules  

---

# 📜 Overview

Each CLB **manager**:

- Declares its own default settings  
- Receives persisted settings merged with its defaults  
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

# 🧰 2. Declaring Default Settings (Manager Side)

Defaults are defined in each manager’s `__init__`:

```python
class Manager(CLBManager):
    def __init__(self, clb):
        super().__init__(clb, defaults={
            "enabled": True,
            "panel_width": 8,
            "panel_height": 8
        })
```

Defaults:

- Provide safe initial values  
- Fill in any missing settings during a firmware upgrade  
- Are merged with persisted settings at startup  

---

# 🔀 3. Startup Settings Merge

During startup (`clb.setup()`):

1. The CLB scans `/managers` for `*_manager.py`  
2. It loads only those managers where `"enabled": true`  
3. It merges persisted settings into each manager's defaults:

```python
merged = defaults.copy()
merged.update(stored_settings)
```

Result:

- Persisted values override defaults  
- All missing fields receive defaults  
- Managers always see a complete `settings` structure  

---

# 🚦 4. Manager Enable/Disable Behaviour

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

# 🧵 5. Nested Settings and Dotted-Path Access

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

# ⚙️ 6. Changing Settings at Runtime

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

# 🛎️ 7. Manager Notification: `on_setting_changed()`

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

# 💾 8. Persistent Saving of Settings

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

# 🧪 9. Resetting Settings to Defaults

The built-in command:

```
reset
```

Overwrites the file with the defaults **for all loaded managers**.

Managers that are disabled do not appear in the reset output.

---

# 🧭 10. Summary

| Stage | Description |
|-------|-------------|
| **Defaults** | Manager declares safe defaults in constructor |
| **Load** | CLB loads `settings.json` and merges with defaults |
| **Enable/Disable** | `"enabled": false` prevents the manager from being instantiated |
| **Setup** | Manager receives its final merged settings during setup |
| **Runtime Updates** | Users update values using dotted paths |
| **Notification** | `on_setting_changed()` is called for live updates |
| **Persistence** | The DeviceConfigurator saves updates immediately |
| **Nested Support** | Arbitrary nesting and list indices are supported |

The CLB settings system is now:

- Robust  
- Extensible  
- Capable of handling nested structures  
- Safe across updates  
- Friendly to both console and remote MQTT configuration  

