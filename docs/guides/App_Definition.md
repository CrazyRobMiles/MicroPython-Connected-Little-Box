# Connected Little Box – Application Definition Guide
### Creating, Configuring, and Selecting Applications

---

## Overview

A Connected Little Box device runs a **firmware image** containing every manager for every application. The active application is determined entirely by `settings.json` — the file on the device that lists which managers to load and how to configure them.

An **application** is a named configuration template stored inside an `App_` manager class. Switching applications means writing a new `settings.json` and rebooting. No firmware changes, no file transfers — just a REPL command.

---

## 1. The Application Manifest

All available applications are registered in `app_manifest.py`:

```python
APPS = [
    {
        "name": "Rotary Encoder Controlled Light",
        "file": "App_lamp",
        "desc": "Uses a Rotary Encoder to control a neopixel panel"
    },
    {
        "name": "Wordsearch Clock",
        "file": "App_wordsearch_clock",
        "desc": "Clock that displays the time using an array of neopixels in a wordsearch."
    },
    ...
]
```

Each entry has three fields:

| Field | Purpose |
|-------|---------|
| `name` | Human-readable name shown by the `apps` command and matched by `select-app` |
| `file` | Module stem — CLB loads `managers.<file>_manager` to find the class |
| `desc` | Short description shown in the app listing |

---

## 2. The App_ Manager Class

Each application is a standard CLB manager whose class name is `Manager`, stored in a file named `App_<something>_manager.py`. App managers inherit from `CLBAppManager` and declare an `app_default_settings` class attribute, which is a **complete `settings.json` template** for the device:

```python
from managers.base_manager import CLBAppManager

class Manager(CLBAppManager):
    version = "1.0.0"
    name = "Rotary Encoder Controlled Light"
    file = "App_lamp"
    desc = "Uses a Rotary Encoder to control a neopixel panel"

    app_default_settings = {
        "pixel": {
            "enabled": True,
            "pixelpin": 18,
            "panel_width": 8,
            "panel_height": 8,
            "x_panels": 1,
            "y_panels": 1,
            "pixeltype": "RGB",
            "animation": "None",
            "panel_type": "Multi-panels-x"
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
            "default_green": 255,
            "default_blue": 255,
            "default_brightness": 1.0,
            "color_encoder_name": "color",
            "brightness_encoder_name": "brightness",
            "brightness_step": 0.05,
            "color_hue_step": 5,
            "dependencies": ["pixel", "rotary_encoder"]
        }
    }

    def __init__(self, clb):
        super().__init__(clb)
```

### Structure of `app_default_settings`

`app_default_settings` is a dictionary of **manager sections**. Each key is a manager name; each value is that manager's configuration:

- Include every manager the application needs, with all required settings
- The App_ manager's own section uses the same key as the manifest `file` value (e.g. `"App_lamp"`)
- List dependencies in the app section's `"dependencies"` list so CLB enforces load order
- Managers not listed are not loaded, so `app_default_settings` defines the complete hardware configuration for the device

---

## 3. REPL Commands

### `apps` — List Available Applications

```
> apps
Applications Available:
   Atom SX70 Remote Manager - Polaroid SX70 remote control for M5Stack Atom with Colour Display.
   Pimoroni GFX Display test application - Tests the display and buttons for a Pimoroni display
   HT16K33 display test application - Tests an HT16k33 display
   Rotary Encoder Controlled Light - Uses a Rotary Encoder to control a neopixel panel
   SX70 Remote Control  - Polaroid SX70 remote control including shutter speed and self timer delay settings
   Wordsearch Clock - Clock that displays the time using an array of neopixels in a wordsearch.
```

Lists every application registered in `app_manifest.py`. This command never modifies the device.

---

### `select-app` — Install an Application

```
> select-app
```

This command:

1. Prints the application list (same as `apps`)
2. Prompts: `Enter the name of the app:`
3. Matches the entered text as a **name prefix** — you only need to type enough to uniquely identify the app
4. Prints the app name and description, then prompts:
   `Configuring this will erase any existing settings. Enter Y to continue, N to abandon:`
5. On `Y`:
   - Loads the App_ manager class for the selected application
   - Reads its `app_default_settings`
   - Writes `app_default_settings` as the entire contents of `settings.json`
   - Counts down five seconds, then calls `machine.reset()`
6. On anything other than `Y`: abandons with no changes

Example session:

```
> select-app
Applications Available:
   Atom SX70 Remote Manager - Polaroid SX70 remote control for M5Stack Atom ...
   Rotary Encoder Controlled Light - Uses a Rotary Encoder to control a neopixel panel
   Wordsearch Clock - Clock that displays the time ...

Enter the name of the app: Rot
Configuring: Rotary Encoder Controlled Light - Uses a Rotary Encoder to control a neopixel panel
Configuring this will erase any existing settings. Enter Y to continue, N to abandon: Y
Performing configuration selection
Configuration updated
Device will reset in five seconds
....0
....1
....2
....3
....4
Reset
```

After the reset, the device boots with the new `settings.json` and loads only the managers listed in the selected application's `default_settings`.

---

## 4. How It Works Internally

```
select-app
    └─ select_application()
           └─ show_applications()        # prints the list
           └─ input()                    # reads name prefix
           └─ find_app_by_prefix()       # matches manifest entry
           └─ configure_app_settings()
                  └─ get_manager_class(file)   # imports managers.<file>_manager
                  └─ mgr.app_default_settings  # reads the class attribute
                  └─ config.settings = ...     # overwrites in-memory settings
                  └─ config.save()             # writes settings.json
                  └─ machine.reset()           # reboots
```

`get_manager_class` imports the module `managers.<file>_manager` and returns the `Manager` class from it. It does **not** instantiate the class — it only reads the `default_settings` class attribute. This means the import must succeed even if the hardware the manager depends on is not connected.

On the next boot, CLB reads the new `settings.json`. Each top-level key that has `"enabled": true` causes CLB to load the corresponding `<key>_manager` module and create an instance.

---

## 5. Creating a New Application

### Step 1 — Write the manager file

Create `firmware/managers/App_myapp_manager.py`. The minimum required structure is:

```python
from managers.base_manager import CLBAppManager

class Manager(CLBAppManager):
    version = "1.0.0"
    name = "My Application"
    file = "App_myapp"
    desc = "Short description shown in the app listing"

    app_default_settings = {
        # --- dependent manager sections ---
        "pixel": {
            "enabled": True,
            "pixelpin": 18,
            "panel_width": 8,
            "panel_height": 8,
            ...
        },
        # --- this app's own section (key must match 'file' value) ---
        "App_myapp": {
            "enabled": True,
            "my_setting": "value",
            "dependencies": ["pixel"]
        }
    }

    def __init__(self, clb):
        super().__init__(clb)

    def setup(self, settings):
        super().setup(settings)
        if not self.enabled:
            return
        # read self.settings as usual

    def setup_services(self):
        # connect to services provided by the dependent managers
        self.pixels = self.get_service_handle("pixel")

    def update(self):
        pass
```

Key points:

- The `file` class attribute **must** match the key in `app_manifest.py` and the key used for this app's own section in `app_default_settings`
- Include every manager the application uses; do not include managers that are not needed
- The `dependencies` list in the app's own section tells CLB the load order

### Step 2 — Register in the manifest

Add an entry to `firmware/app_manifest.py`:

```python
APPS = [
    ...
    {
        "name": "My Application",
        "file": "App_myapp",
        "desc": "Short description shown in the app listing"
    },
]
```

The `name` here must match the class attribute `name` exactly (it is also used for prefix matching by `select-app`).

### Step 3 — Test

Upload the firmware, connect to the REPL, and run:

```
> apps
```

The new application should appear. Then:

```
> select-app
Enter the name of the app: My
```

If the configuration is applied and the device reboots into the correct set of managers, the application is working.

---

## 6. Application Settings vs Runtime Settings

`default_settings` defines the **starting point** for a device's configuration. Once `select-app` has written it to `settings.json`, individual settings can be changed with the `set` command without re-running `select-app`:

```
set pixel.panel_width=16
set App_myapp.my_setting=newvalue
```

These changes are persisted to `settings.json` immediately. Running `select-app` again will overwrite them with the template defaults, so use it only to switch to a completely different hardware configuration.

To restore defaults for the currently running application without switching, use the `reset` command:

```
> reset
```

This resets each loaded manager to its own `default_settings` values, but it does not remove managers or add new ones.

---

## 7. Summary

| Concept | Description |
|---------|-------------|
| `app_manifest.py` | Registry of all available applications — name, file stem, description |
| `App_xxx_manager.py` | Manager file holding the application logic and its `app_default_settings` template |
| `app_default_settings` | Complete `settings.json` template — every dependent manager section included |
| `file` attribute | Must match the manifest entry and the app's own settings section key |
| `apps` command | Lists all registered applications without modifying anything |
| `select-app` command | Writes the selected app's `app_default_settings` to `settings.json` and reboots |
| `reset` command | Restores per-manager defaults for the currently running set of managers |
| `set` command | Changes individual settings and persists them without rebooting |
