from managers.base_manager import CLBAppManager


class Manager(CLBAppManager):
    version = "1.0.0"
    name = "Button Light"
    file = "App_button_light"
    desc = "Lights up pixels when a button is pressed, off when released"

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
        "gpio": {
            "enabled": True,
            "input_pins": [{"name": "button", "pin": 14}],
            "output_pins": [],
            "default_debounce_ms": 20,
            "pullup": True
        },
        "App_button_light": {
            "enabled": True,
            "on_red": 255,
            "on_green": 100,
            "on_blue": 0,
            "dependencies": ["pixel", "gpio"]
        }
    }

    def __init__(self, clb):
        super().__init__(clb)
        self.pixels = None

    def setup(self, settings):
        super().setup(settings)
        if not self.enabled:
            self.state = self.STATE_DISABLED
            return
        self.on_red   = self.settings.get("on_red",   255)
        self.on_green = self.settings.get("on_green", 100)
        self.on_blue  = self.settings.get("on_blue",    0)
        self.state = self.STATE_OK
        self.set_status(1001, "Button Light ready")

    def setup_services(self):
        self.pixels = self.get_service_handle("pixel")
        if self.pixels:
            self.pixels.fill(0, 0, 0)

        button_pressed = self.clb.get_event("gpio.button_low")
        if button_pressed:
            button_pressed.subscribe(self.on_button_pressed)

        button_released = self.clb.get_event("gpio.button_high")
        if button_released:
            button_released.subscribe(self.on_button_released)

    def on_button_pressed(self, event, data):
        if self.pixels:
            self.pixels.fill(self.on_red, self.on_green, self.on_blue)

    def on_button_released(self, event, data):
        if self.pixels:
            self.pixels.fill(0, 0, 0)

    def update(self):
        if not self.enabled:
            return
