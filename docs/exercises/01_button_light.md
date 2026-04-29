# Exercise 01: Button Light

## What You Will Build

A strip of NeoPixel LEDs that light up when you press a button and go off when you release it.

That is the complete brief. By the end of this exercise you will have built it — not by copying a solution, but by assembling it from parts you understand.

## What You Will Learn

- What the Connected Little Box (CLB) framework is and why it is structured the way it is
- What a *manager* is and how its lifecycle works
- How a device is configured using JSON settings
- What an *application* is and how it differs from a hardware driver
- How managers communicate through *services* and *events*
- How to assemble multiple managers into a working application

## Hardware Required

- A Raspberry Pi Pico (or compatible RP2040 board)
- A strip of at least 8 NeoPixel (WS2812) LEDs connected to GPIO pin 18
- A tactile push button connected between GPIO pin 14 and GND (the pin has a software pull-up, so no external resistor is needed)
- USB connection to a computer running Thonny or similar

---

# Part 1: The Framework

## What is the Connected Little Box?

The CLB is a MicroPython framework for building small connected devices. Its central idea is that **every capability of the device is implemented as a manager** — a self-contained Python class responsible for one thing. The WiFi connection is a manager. The NeoPixel strip is a manager. The button is a manager. Your application logic is also a manager.

These managers run cooperatively. There is no operating system, no threads, and no interrupts doing heavy work. Instead, every manager gets a turn in a tight loop:

```
while True:
    for each manager:
        manager.update()
```

This means **every `update()` must return quickly** — typically in under a millisecond. If one manager blocks, the whole device freezes. You will see how to handle time-consuming behaviour later using Python's `yield`.

## The Manager Lifecycle

Every manager goes through the same sequence of calls:

```
setup(settings)        ← called once at boot, initialise hardware
setup_services()       ← called after all managers are set up,
                          connect to other managers here
update()               ← called every loop, do ongoing work here
teardown()             ← called on shutdown (optional)
```

`setup()` is where you initialise hardware and read your settings.  
`setup_services()` is where you connect to other managers — subscribe to their events, get handles to their services.  
`update()` must be fast. Use `yield` if you need to wait.

## The Settings System

Every manager stores its configuration in a central file called `settings.json` on the device. A typical entry looks like this:

```json
{
    "pixel": {
        "enabled": true,
        "pixelpin": 18,
        "panel_width": 8,
        "panel_height": 1
    },
    "gpio": {
        "enabled": true,
        "input_pins": [{"name": "button", "pin": 14}]
    }
}
```

Each top-level key is a manager name. If `"enabled"` is `true`, CLB loads that manager at boot. If it is `false` or the key is absent entirely, the manager is not loaded at all.

Managers declare their own default settings as a class attribute. When CLB loads `settings.json`, it merges the stored values with the defaults — any key that is missing from the file is filled in from the defaults automatically.

You can change a setting live from the REPL without editing any file:

```
set pixel.panel_width=16
```

The change is saved to `settings.json` immediately and survives reboot.

## Applications vs Device Managers

There are two kinds of manager:

**Device managers** handle one piece of hardware or one system service. The pixel manager drives the NeoPixel strip. The GPIO manager watches input pins. Each lives in a file like `pixel_manager.py` and uses `CLBDeviceManager` as its base class.

**Application managers** define a complete working device configuration. They declare — in a single class attribute called `app_default_settings` — the full `settings.json` template: every device manager the application needs, with all their settings, plus the application's own configuration. They use `CLBAppManager` as their base class and live in files starting with `App_`.

Think of `app_default_settings` as the **bill of materials** for a specific device. Loading an application writes that bill of materials to `settings.json` and reboots. From that point, CLB loads exactly the managers that application needs and nothing else.

You switch between applications with a single REPL command:

```
select-app
```

This lists all registered applications and asks you to choose one by name.

---

# Part 2: Create the Skeleton Application

Open `App_button_light_empty_manager.py` in Thonny. It contains a minimal working application with no behaviour yet:

```python
from managers.base_manager import CLBAppManager

class Manager(CLBAppManager):
    version = "1.0.0"
    name = "Button Light"
    file = "App_button_light"
    desc = "Lights up pixels when a button is pressed"

    app_default_settings = {
        "App_button_light": {
            "enabled": True,
            "dependencies": []
        }
    }

    def __init__(self, clb):
        super().__init__(clb)

    def setup(self, settings):
        super().setup(settings)
        if not self.enabled:
            self.state = self.STATE_DISABLED
            return
        self.state = self.STATE_OK
        self.set_status(1001, "Button Light ready")

    def update(self):
        if not self.enabled:
            return
```

Make a copy of this file and name it `App_button_light_manager.py`. This is the file you will build on. Save it to the device.

Now load it from the REPL:

```
select-app Button Light
```

The device reboots. When it comes back up, check the manager status:

```
status
```

**What you should see:** The `App_button_light` manager appears in the list with state `ok`. No other managers are loaded. Nothing visible happens — the application has no hardware yet.

### Think About It

- Why does only `App_button_light` appear? Look at `app_default_settings` — what does it say to load?
- What would you need to add to make the `pixel` manager load?
- The `update()` method currently returns immediately. What would happen if it contained `time.sleep(1)`?

---

# Part 3: Add the Pixel Manager

The pixel manager drives the NeoPixel strip. To use it, your application needs to do two things:

1. **Declare it** in `app_default_settings` so CLB loads it at boot
2. **Get a service handle** to it in `setup_services()` so you can call its functions

### Services

Device managers expose their capabilities as *services* — a dictionary of named functions returned by `get_interface()`. The pixel manager exposes functions like `fill`, `set_rgb`, `show`, and others.

You access these from another manager using `get_service_handle()`:

```python
self.pixels = self.get_service_handle("pixel")
```

This returns a proxy object. Calling `self.pixels.fill(255, 100, 0)` is equivalent to calling the pixel manager's `fill` function with those arguments.

### Modify Your App

Add the pixel section to `app_default_settings`. Your settings block should now look like this:

```python
app_default_settings = {
    "pixel": {
        "enabled": True,
        "pixelpin": 18,
        "panel_width": 8,
        "panel_height": 1,
        "x_panels": 1,
        "y_panels": 1,
        "pixeltype": "RGB",
        "animation": "None",
        "panel_type": "Multi-panels-x"
    },
    "App_button_light": {
        "enabled": True,
        "on_red": 255,
        "on_green": 100,
        "on_blue": 0,
        "dependencies": ["pixel"]
    }
}
```

Note two things: the `on_red`, `on_green`, `on_blue` settings define the colour you will use later, and `"pixel"` has been added to `dependencies` so CLB initialises the pixel manager before your application.

Now add `setup_services()` to your class — this goes after `setup()`:

```python
def setup_services(self):
    self.pixels = self.get_service_handle("pixel")
    if self.pixels:
        self.pixels.fill(0, 0, 0)
```

And add `self.pixels = None` to `__init__`:

```python
def __init__(self, clb):
    super().__init__(clb)
    self.pixels = None
```

Save the file. Now reload the application:

```
select-app Button Light
```

**What you should see:** The device reboots. Now `status` shows both `pixel` and `App_button_light` in state `ok`. The pixel strip should initialise (it may flash briefly) and settle to off.

Try calling the pixel service directly from the REPL:

```
pixel.fill 255 0 0
```

The strip should turn red. Turn it off again:

```
pixel.fill 0 0 0
```

### Think About It

- You called `pixel.fill` from the REPL just like your code will call it. The REPL and your manager use the same service interface. Why is that consistent design useful?
- What does `get_service_handle("pixel")` return if the pixel manager failed to initialise? Why does the `if self.pixels:` guard matter?
- The pixel settings are inside your `app_default_settings`. Who owns those settings — your app or the pixel manager?

---

# Part 4: Add the Button

You now have a working output. The final step is connecting an input to it. The GPIO manager watches input pins and, when a pin changes state, **publishes an event**.

### Events

An event is a named signal. Any manager can subscribe to any event by name. When the event fires, every subscriber's handler function is called with `(event, data)`.

This is the publish/subscribe pattern. The GPIO manager does not know or care who is listening. Your application does not know or care how the GPIO manager detected the change. They are connected only by a name — a string.

The GPIO manager names its events using a consistent pattern:

```
gpio.<pin_name>_low     ← pin went low (button pressed, with pull-up)
gpio.<pin_name>_high    ← pin went high (button released)
```

Your pin is named `"button"` in the settings. So the events are `gpio.button_low` and `gpio.button_high`.

### Modify Your App

Add the `gpio` section to `app_default_settings`:

```python
"gpio": {
    "enabled": True,
    "input_pins": [{"name": "button", "pin": 14}],
    "output_pins": [],
    "default_debounce_ms": 20,
    "pullup": True
},
```

Add `"gpio"` to the dependencies list:

```python
"dependencies": ["pixel", "gpio"]
```

Read the colour settings in `setup()`, after the `STATE_OK` line:

```python
self.on_red   = self.settings.get("on_red",   255)
self.on_green = self.settings.get("on_green", 100)
self.on_blue  = self.settings.get("on_blue",    0)
```

Add the two event subscriptions to `setup_services()`:

```python
button_pressed = self.clb.get_event("gpio.button_low")
if button_pressed:
    button_pressed.subscribe(self.on_button_pressed)

button_released = self.clb.get_event("gpio.button_high")
if button_released:
    button_released.subscribe(self.on_button_released)
```

Add the two handler methods to your class:

```python
def on_button_pressed(self, event, data):
    if self.pixels:
        self.pixels.fill(self.on_red, self.on_green, self.on_blue)

def on_button_released(self, event, data):
    if self.pixels:
        self.pixels.fill(0, 0, 0)
```

Save. Reload:

```
select-app Button Light
```

**What you should see:** Press the button — the pixels light up. Release — they go off. The application is complete.

### Think About It

- Your `on_button_pressed` handler calls `self.pixels.fill()`. The pixel manager has no idea a button exists anywhere on the device. The GPIO manager has no idea pixels exist. What makes this possible?
- What would happen if you subscribed a second handler to `gpio.button_low` — for example, one that played a sound? Would you need to change anything in the GPIO manager?
- The `update()` method in your application is empty. All the work happens in event handlers. Is this typical? What kind of work *would* belong in `update()`?

---

# Part 5: Customise and Explore

Your application now works. These changes require only a `set` command — no code edits and no reboot:

**Change the colour:**
```
set App_button_light.on_red=0
set App_button_light.on_green=0
set App_button_light.on_blue=255
```
Press the button. The pixels are now blue. The new values are saved to `settings.json` and will survive reboot.

**Change the number of pixels:**
```
set pixel.panel_width=4
```
Reboot. Only four pixels light up.

Now try some code changes in Thonny:

- Make the pixels turn a different colour on long press (you will need to track time in `update()`)
- Make the pixels fade out gradually after release instead of turning off immediately
- Subscribe to both `button_low` and `button_high` with a single handler that uses `data` to determine which event fired

---

# Using the AI Assistant

If this class has AI assistance available, you can use the `ask` command from the REPL:

```
ask <your question>
```

The assistant knows what this exercise is about and what you are expected to figure out yourself. Getting useful help requires describing what you observe precisely:

**Not useful:**
```
ask it doesn't work
```

**Useful:**
```
ask the pixel manager shows STATE_OK in the status output but when I press
the button nothing happens. There are no errors in the console. The gpio
manager also shows STATE_OK.
```

The second description tells the assistant: what you expected, what actually happened, what you have already checked, and what the relevant manager states are. That is enough to diagnose most problems.

If you are not sure what to observe, check:

1. `status` — what state is each manager in?
2. The console output since the last reboot — any errors?
3. Whether the event is firing at all (add `print("button pressed")` to your handler temporarily)
4. Whether the service call is reaching the pixel manager (try calling `pixel.fill 255 0 0` directly from the REPL)

Forming a precise description of a broken system is itself an engineering skill. The discipline of separating *what I expected* from *what I observed* from *what I have already tried* is the same process used to write a useful bug report, ask a useful question on a forum, or brief a colleague on a problem.

---

# Reference: What You Built

```
┌─────────────────────────────────────────────────────┐
│  App_button_light  (CLBAppManager)                  │
│                                                     │
│  app_default_settings defines:                      │
│    pixel  ──► pixelpin, panel_width, ...            │
│    gpio   ──► input_pins: [{name:"button", pin:14}] │
│    App_button_light ──► on_red, on_green, on_blue   │
│                                                     │
│  setup_services():                                  │
│    get_service_handle("pixel") ──► self.pixels      │
│    subscribe gpio.button_low  ──► on_button_pressed │
│    subscribe gpio.button_high ──► on_button_released│
│                                                     │
│  on_button_pressed:  pixels.fill(r, g, b)           │
│  on_button_released: pixels.fill(0, 0, 0)           │
└─────────────────────────────────────────────────────┘
         │ service call              │ event subscription
         ▼                          ▼
┌─────────────────┐      ┌──────────────────────┐
│ pixel manager   │      │ gpio manager         │
│ (CLBDeviceManager)     │ (CLBDeviceManager)   │
│                 │      │                      │
│ fill(r,g,b)     │      │ publishes:           │
│ set_rgb(x,y,...)│      │  gpio.button_low     │
│ show()          │      │  gpio.button_high    │
└─────────────────┘      └──────────────────────┘
```

The pixel manager does not know the button exists.  
The GPIO manager does not know the pixels exist.  
Your application connects them — and is the only place that knows about both.

This separation is the same pattern used in professional embedded systems, distributed services, and event-driven architectures at any scale.
