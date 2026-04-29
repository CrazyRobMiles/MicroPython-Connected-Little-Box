# 🧩 Connected Little Box – How Managers Work  
### A Guide to Writing CLB Managers (Using the Blink Manager as an Example)

Managers are the fundamental building blocks of the Connected Little Box (CLB) system.  
Every subsystem—pixels, WiFi, MQTT, steppers, displays, scripting, and more—is implemented as a **manager**.

This document explains:

- What a manager is  
- How the CLB lifecycle works  
- How states, settings, and dependencies function  
- How to expose commands/services  
- How to write your own manager using the **Blink Manager** as an example  

---
# IMPORTANT 
The Connected Little Boxes framework is a **cooperative** multi tasking environment. Each manager must update as quickly as possible otherwise the performance of the whole device will suffer. All the supplied managers usually complete in around 50 milliseconds or less. You can use the Python yield construction to allow manager updates to maintain state. 
---

# 📘 1. What Is a Manager?

A **manager** is a Python class that inherits from `CLBDeviceManager` or `CLBAppManager` and provides:

- **Setup logic** (run on device boot)
- **Update logic** (run continuously during the main loop)
- **Services** (commands accessible from console, MQTT, scripts, etc.)
- **Status messages**
- **Persistent settings**
- **Dependency control**
- **Graceful teardown**

Each manager lives in:

```
/managers/<name>_manager.py
```

and contains one class named `Manager`. There are two base classes to choose from:

| Base class | Use for |
|------------|---------|
| `CLBDeviceManager` | Hardware/service managers (pixels, WiFi, GPIO, sensors, …) |
| `CLBAppManager` | Application managers (`App_` files — define a complete device configuration) |

Managers allow the CLB system to remain modular, extensible, and hardware-independent.

---

# 🔄 2. The Manager Lifecycle

The CLB boot process loads and initialises all managers in order:

```
Load manager → Merge settings → setup() → build interface → setup_services()
```

During runtime:

```
update() is called continuously
```

On shutdown:

```
teardown() is called
```

### Manager Lifecycle Diagram

```
          ┌──────────┐
          │ Defaults │
          └────┬─────┘
               │
      Load settings.json
               │
               ▼
        ┌─────────────┐
        │  setup()    │  ← initialise hardware, merge settings
        └──────┬──────┘
               │
               ▼
        ┌──────────────────────┐
        │  setup_services()    │  ← bind to events and create service proxies
        └──────┬───────────────┘
               │
     Build unified interface
               │
               ▼
       ┌─────────────┐
       │ update()    │  ← runs every loop
       └───────┬─────┘
               │
        Optional teardown()
```

---

# 🧠 3. Manager States

All managers should use:

### **STATE_OK**
Set when the manager has initialised correctly and is ready for use.

### **STATE_DISABLED**
Set when:
- The manager is turned off via settings  
- The user runs a disable command  

### **STATE_ERROR**
Set when setup fail or a manager fails during operation (for example when a WiFi connection fails)

### Why it matters  
Other managers may depend on yours.  
For example, the MQTT manager waits until WiFi is in `STATE_OK`.

---

# ⚙️ 4. Settings

Each manager declares its defaults as a **class attribute**. Device managers use `device_default_settings`:

```python
class Manager(CLBDeviceManager):
    device_default_settings = {
        "pin": "LED",
        "delay_seconds": 1.0,
    }

    def __init__(self, clb):
        super().__init__(clb)   # no defaults argument
```

CLB merges these defaults with `/settings.json` at startup — any key present in `device_default_settings` but missing from the stored settings is filled in automatically.

Access the merged values through:

```python
self.settings["pin"]
self.settings["delay_seconds"]
```

Managers **should not write** their settings directly — saving is handled by CLB + DeviceConfigurator.

---

# 🔌 5. Exposing Commands (Service Interface)

Managers may expose commands to the CLB interface using `get_interface()`:

```python
def get_interface(self):
    return {
        "start": ("Start blinking", self.cmd_start),
        "stop":  ("Stop blinking", self.cmd_stop),
    }
```

Users call these from the CLB console using **Python function-call syntax** — the same syntax used to call methods in code:

```
blink.start()
blink.stop()
```

Commands that accept arguments are called exactly as you would call a Python function:

```
pixel.fill(255, 0, 0)
pixel.mode("wordsearch")
stepper.move(100)
```

Named (keyword) arguments also work if the underlying method supports them:

```
pixel.fill(red=255, green=0, blue=0)
```

A bare name with no parentheses is treated as a zero-argument call, so `blink.start` and `blink.start()` are equivalent.

This design is intentional: the console command and the equivalent Python code look the same, making it easy to graduate from typing commands at the prompt to writing them in a script.

---

# 🪝 6. Dependencies Between Managers

Managers can declare:

```python
dependencies = ["wifi"]
```

CLB ensures:

- Managers load in dependency order
- `update()` is not fully processed until dependencies are in `STATE_OK`

This enables managers to cleanly rely on network connectivity, displays, pixel hardware, etc.

---

# 💡 7. Example: The Blink Manager

The Blink Manager is a simple example that:

- Uses settings (`pin`, `delay_seconds`)
- Uses a coroutine (`yield`-style blinking)
- Exposes two commands (`start`, `stop`)
- Demonstrates `STATE_OK`
- Controls the built-in Pico LED

---

# 🧱 8. Blink Manager Code (Annotated)

```python
from managers.base_manager import CLBDeviceManager
import machine
import time


class Manager(CLBDeviceManager):
    version = "1.0.1"

    STATE_DISABLED = "disabled"
    STATE_IDLE     = "idle"

    device_default_settings = {
        "pin": "LED",             # Default Pico LED
        "delay_seconds": 1.0,     # Blink once per second
    }

    def __init__(self, clb):
        super().__init__(clb)
        self.state = self.STATE_IDLE
        self._gen  = None
        self.led   = None
```

### ✔ Setup

```python
    def setup(self, settings):
        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        try:
            pin_setting = self.settings["pin"]
            self.delay = float(self.settings["delay_seconds"])

            # Allow pin name ("LED") or number (25)
            if isinstance(pin_setting, str):
                self.led = machine.Pin(pin_setting, machine.Pin.OUT)
            else:
                self.led = machine.Pin(int(pin_setting), machine.Pin.OUT)

            self.led.value(0)

            self.state = self.STATE_OK
            self.set_status(6001, f"Blink manager OK on pin {pin_setting}")

        except Exception as e:
            self.state = self.STATE_ERROR
            self.set_status(6002, f"Blink setup error: {e}")
```
The blink manager does not use any other events or services and so the blink manager doesn't contain a setup_services method.

### ✔ Coroutine for Blinking

```python
    def _blink_coroutine(self):
        delay_ms = int(self.delay * 1000)

        while True:
            self.led.value(1)
            start = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), start) < delay_ms:
                yield

            self.led.value(0)
            start = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), start) < delay_ms:
                yield
```

### ✔ Start and Stop Commands

```python
    def start(self):
        self._gen = self._blink_coroutine()
        self.state = self.STATE_OK
        self.set_status(6003, "Blink started")

    def stop(self):
        self._gen = None
        if self.led:
            self.led.value(0)
        self.state = self.STATE_OK
        self.set_status(6004, "Blink stopped")
```

### ✔ Update Loop

```python
    def update(self):
        if self._gen:
            try:
                next(self._gen)
            except StopIteration:
                self._gen = None
                self.state = self.STATE_OK
```
The blink manager uses the Python `yield` construction to hand off execution to the next task. If a call to the `update` function doesn't return the whole device will be locked up. 

### ✔ Exposed Commands

```python
    def get_interface(self):
        return {
            "start": ("Start blinking", self.start),
            "stop":  ("Stop blinking", self.stop),
        }
```

---

# 🛠️ 9. How to Write Your Own Manager

To create a new manager:

---

## **Step 1 — Create the file**

Example:

```
/managers/temp_sensor_manager.py
```

---

## **Step 2 — Define the class**

```python
from managers.base_manager import CLBDeviceManager
import machine

class Manager(CLBDeviceManager):
    version = "1.0.0"
```

---

## **Step 3 — Declare defaults**

```python
    device_default_settings = {
        "enabled": True,
        "pin": 4,
        "interval": 2.0
    }

    def __init__(self, clb):
        super().__init__(clb)
```

---

## **Step 4 — Implement `setup()`**

```python
def setup(self, settings):
    super().setup(settings)

    if not self.enabled:
        self.state = self.STATE_DISABLED
        return

    self.sensor = machine.ADC(self.settings["pin"])
    self.state = self.STATE_OK
```

---

## **Step 5 — Implement `update()`**

```python
def update(self):
    if self.state != self.STATE_OK:
        return

    reading = self.sensor.read_u16()
    # do something...
```

---

## **Step 6 — Expose commands**

```python
def get_interface(self):
    return {
        "read": ("Read temperature", self.cmd_read)
    }

def cmd_read(self):
    return self.sensor.read_u16()
```

---

# 🧭 10. Summary Checklist for All New Managers

| Feature | Required? | Notes |
|--------|-----------|-------|
| `device_default_settings` | ✔ | Class attribute; include `”enabled”` key |
| `setup()` | ✔ | Must set `STATE_OK` on success |
| `update()` | ✔ | Called every cycle |
| `get_interface()` | Optional | For user commands |
| Settings access | ✔ | From `self.settings` |
| Proper states | ✔ | OK / disabled / error |
| Dependencies | Optional | Declared in settings `”dependencies”` list |
| Teardown | Optional | Release hardware if needed |

---

# 🎉 You Can Now Build Your Own CLB Managers!

The Blink Manager demonstrates:

- Hardware access  
- Settings  
- Yield-based cooperative multitasking  
- Command exposure  
- Proper state handling  

With this pattern, you can confidently build:

- Input managers (buttons, rotary encoders)  
- Output managers (servos, relays, LEDs)  
- Network managers  
- Display managers  
- Animation controllers  
- Script engines  
- Sensors  

Anything can become a manager.

---

If you'd like:

- A PDF version  
- A “manager template” file  
- A guided exercise (“build a temperature manager”)  

Just tell me!

