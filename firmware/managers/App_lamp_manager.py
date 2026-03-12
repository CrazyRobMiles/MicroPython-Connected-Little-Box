from managers.base_manager import CLBManager


class Manager(CLBManager):
    version = "1.0.0"

    def __init__(self, clb):
        super().__init__(clb, defaults={
            "default_red": 255,
            "default_green": 255,
            "default_blue": 255,
            "default_brightness": 1.0,
            "color_encoder_name": "color",
            "brightness_encoder_name": "brightness",
            "brightness_step": 0.05,
            "color_hue_step": 5
        })
        self.pixel_service = None
        self.rotary_encoder_service = None
        self.current_red = 255
        self.current_green = 255
        self.current_blue = 255
        self.current_brightness = 1.0
        self.current_hue = 0
        self.color_encoder_name = None
        self.brightness_encoder_name = None

    def setup(self, settings):
        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        # Load defaults from settings
        self.current_red = self.settings.get("default_red", 255)
        self.current_green = self.settings.get("default_green", 255)
        self.current_blue = self.settings.get("default_blue", 255)
        self.current_brightness = self.settings.get("default_brightness", 1.0)
        self.color_encoder_name = self.settings.get("color_encoder_name", "color")
        self.brightness_encoder_name = self.settings.get("brightness_encoder_name", "brightness")

        # Clamp brightness to 0.0 - 1.0
        self.current_brightness = max(0.0, min(1.0, self.current_brightness))

        self.state = self.STATE_OK
        self.set_status(7001, "Lamp App manager ready")

    def setup_services(self):
        """Connect to pixel and rotary encoder services"""
        # Get pixel service
        self.pixel_service = self.get_service_handle("pixel")
        if self.pixel_service:
            print("[Lamp] Connected to pixel service")
            # Set initial color and brightness
            self._apply_color()
        else:
            print("[Lamp] Pixel service unavailable")

        # Subscribe to encoder events
        self._subscribe_to_encoders()

    def _subscribe_to_encoders(self):
        """Subscribe to encoder events"""
        if not self.clb:
            print("[Lamp] No CLB reference available")
            return

        # Subscribe to color encoder events
        color_cw_event = self.clb.get_event(f"rotary_encoder.{self.color_encoder_name}_moved_clockwise")
        color_acw_event = self.clb.get_event(f"rotary_encoder.{self.color_encoder_name}_moved_anticlockwise")

        if color_cw_event:
            color_cw_event.subscribe(self._on_color_clockwise)
        if color_acw_event:
            color_acw_event.subscribe(self._on_color_anticlockwise)

        # Subscribe to brightness encoder events
        brightness_cw_event = self.clb.get_event(f"rotary_encoder.{self.brightness_encoder_name}_moved_clockwise")
        brightness_acw_event = self.clb.get_event(f"rotary_encoder.{self.brightness_encoder_name}_moved_anticlockwise")

        if brightness_cw_event:
            brightness_cw_event.subscribe(self._on_brightness_clockwise)
        if brightness_acw_event:
            brightness_acw_event.subscribe(self._on_brightness_anticlockwise)

        print("[Lamp] Subscribed to encoder events")

    def _on_color_clockwise(self, event, data):
        """Handle color encoder clockwise rotation"""
        hue_step = self.settings.get("color_hue_step", 5)
        self.current_hue = (self.current_hue + hue_step) % 360
        self._update_rgb_from_hue()
        self._apply_color()

    def _on_color_anticlockwise(self, event, data):
        """Handle color encoder counter-clockwise rotation"""
        hue_step = self.settings.get("color_hue_step", 5)
        self.current_hue = (self.current_hue - hue_step) % 360
        self._update_rgb_from_hue()
        self._apply_color()

    def _on_brightness_clockwise(self, event, data):
        """Handle brightness encoder clockwise rotation (increase brightness)"""
        brightness_step = self.settings.get("brightness_step", 0.05)
        self.current_brightness = min(1.0, self.current_brightness + brightness_step)
        self._apply_color()

    def _on_brightness_anticlockwise(self, event, data):
        """Handle brightness encoder counter-clockwise rotation (decrease brightness)"""
        brightness_step = self.settings.get("brightness_step", 0.05)
        self.current_brightness = max(0.0, self.current_brightness - brightness_step)
        self._apply_color()

    def _update_rgb_from_hue(self):
        """Convert HSV (using current hue with full saturation and value) to RGB"""
        # Simple HSV to RGB conversion with saturation=1.0 and value=1.0
        hue = self.current_hue
        c = 1.0  # chroma (saturation * value)

        h_prime = hue / 60.0
        x = c * (1.0 - abs((h_prime % 2.0) - 1.0))

        if h_prime < 1.0:
            r, g, b = c, x, 0.0
        elif h_prime < 2.0:
            r, g, b = x, c, 0.0
        elif h_prime < 3.0:
            r, g, b = 0.0, c, x
        elif h_prime < 4.0:
            r, g, b = 0.0, x, c
        elif h_prime < 5.0:
            r, g, b = x, 0.0, c
        else:
            r, g, b = c, 0.0, x

        # Convert to 0-255 range
        self.current_red = int(r * 255)
        self.current_green = int(g * 255)
        self.current_blue = int(b * 255)

    def _apply_color(self):
        """Apply current color and brightness to the pixel panel"""
        if not self.pixel_service:
            return

        # Apply brightness scaling
        scaled_red = int(self.current_red * self.current_brightness)
        scaled_green = int(self.current_green * self.current_brightness)
        scaled_blue = int(self.current_blue * self.current_brightness)

        try:
            self.pixel_service.fill(scaled_red, scaled_green, scaled_blue)
            print(f"[Lamp] Color: RGB({scaled_red}, {scaled_green}, {scaled_blue}) Brightness: {self.current_brightness:.2f}")
        except Exception as e:
            print(f"[Lamp] Error applying color: {e}")

    def update(self):
        """Called on each update cycle"""
        if not self.enabled or self.state != self.STATE_OK:
            return

    def get_interface(self):
        """Return exposed commands"""
        return {
            "set_color": ("set_color <r> <g> <b>", self.command_set_color),
            "set_brightness": ("set_brightness <0.0-1.0>", self.command_set_brightness),
            "status": ("status", self.command_status),
        }

    def command_set_color(self, r, g, b):
        """Set color directly"""
        try:
            self.current_red = int(r)
            self.current_green = int(g)
            self.current_blue = int(b)
            self._apply_color()
        except Exception as e:
            print(f"[Lamp] Error setting color: {e}")

    def command_set_brightness(self, brightness):
        """Set brightness directly"""
        try:
            self.current_brightness = max(0.0, min(1.0, float(brightness)))
            self._apply_color()
        except Exception as e:
            print(f"[Lamp] Error setting brightness: {e}")

    def command_status(self):
        """Print current lamp status"""
        print(f"[Lamp] Status:")
        print(f"  Color: RGB({self.current_red}, {self.current_green}, {self.current_blue})")
        print(f"  Hue: {self.current_hue:.1f}°")
        print(f"  Brightness: {self.current_brightness:.2f}")
        print(f"  Color Encoder: {self.color_encoder_name}")
        print(f"  Brightness Encoder: {self.brightness_encoder_name}")

    def teardown(self):
        """Clean up on shutdown"""
        self.set_status(7012, "Lamp manager torn down")
