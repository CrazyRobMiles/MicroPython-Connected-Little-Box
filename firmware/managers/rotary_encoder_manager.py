from managers.base_manager import CLBManager
from managers.event import Event
import machine
import time


class Manager(CLBManager):
    version = "1.0.0"

    def __init__(self, clb):
        super().__init__(clb, defaults={
            "encoders": []
        })
        self.encoders = {}  # {encoder_name: EncoderHandler}
        self.events = {}    # {event_name: Event object}

    def setup(self, settings):
        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        self.state = self.STATE_OK
        self.set_status(6101, "Rotary encoder manager ready")

    def setup_services(self):
        """Called after all managers are set up. Connect to event manager."""
        # Configure encoders from settings
        encoders_config = self.settings.get("encoders", [])
        for encoder_config in encoders_config:
            self._configure_encoder(encoder_config)

    def _configure_encoder(self, encoder_config):
        """Configure a rotary encoder from a config dict"""
        if not isinstance(encoder_config, dict):
            print(f"[RotaryEncoder] Invalid encoder config: {encoder_config}")
            return

        encoder_name = encoder_config.get("name")
        clk_pin = encoder_config.get("clk_pin")
        dt_pin = encoder_config.get("dt_pin")
        btn_pin = encoder_config.get("btn_pin")

        if not encoder_name or clk_pin is None or dt_pin is None:
            print(f"[RotaryEncoder] Encoder config missing name, clk_pin, or dt_pin")
            return

        try:
            encoder = EncoderHandler(
                name=encoder_name,
                clk_pin=clk_pin,
                dt_pin=dt_pin,
                btn_pin=btn_pin,
                manager=self
            )
            self.encoders[encoder_name] = encoder
            self._create_encoder_events(encoder_name)
            print(f"[RotaryEncoder] Configured encoder '{encoder_name}' (CLK: {clk_pin}, DT: {dt_pin}, BTN: {btn_pin})")
        except Exception as e:
            print(f"[RotaryEncoder] Failed to configure encoder '{encoder_name}': {e}")

    def _create_encoder_events(self, encoder_name):
        """Create events for a specific encoder"""
        event_names = [
            f"rotary_encoder.{encoder_name}_connected",
            f"rotary_encoder.{encoder_name}_moved_clockwise",
            f"rotary_encoder.{encoder_name}_moved_anticlockwise",
            f"rotary_encoder.{encoder_name}_button_pressed"
        ]

        for event_name in event_names:
            if event_name not in self.events:
                self.events[event_name] = Event(
                    name=event_name,
                    description=f"Rotary encoder '{encoder_name}' event: {event_name.split('_', 1)[1]}",
                    owner=self
                )

    def get_event(self, event_name):
        """Get an event object by name for subscription"""
        return self.events.get(event_name)

    def publish_event(self, event_name, data=None):
        """Publish an event with data"""
        if event_name in self.events:
            self.events[event_name].publish(data)

    def update(self):
        """Called on each manager update cycle to poll encoder inputs"""
        if not self.enabled or self.state != self.STATE_OK:
            return

        # Update each encoder
        for encoder_name, encoder in self.encoders.items():
            encoder.update(self)

    def get_interface(self):
        """Return exposed commands"""
        return {
            "list": ("list", self.command_list_encoders),
            "status": ("status <name>", self.command_encoder_status),
        }

    def command_list_encoders(self):
        """List all configured encoders"""
        if not self.encoders:
            print("[RotaryEncoder] No encoders configured")
            return

        for encoder_name in self.encoders:
            print(f"  - {encoder_name}")

    def command_encoder_status(self, encoder_name=""):
        """Get status of a specific encoder"""
        if not encoder_name:
            print("[RotaryEncoder] Please provide encoder name")
            return

        encoder = self.encoders.get(encoder_name)
        if not encoder:
            print(f"[RotaryEncoder] Encoder '{encoder_name}' not found")
            return

        print(f"[RotaryEncoder] {encoder_name}:")
        print(f"  CLK Pin: {encoder.clk_pin}")
        print(f"  DT Pin: {encoder.dt_pin}")
        print(f"  Button Pin: {encoder.btn_pin}")
        print(f"  Last CLK State: {encoder.last_clk_state}")
        print(f"  Last DT State: {encoder.last_dt_state}")
        print(f"  Last Button State: {encoder.last_btn_state}")

    def teardown(self):
        """Clean up encoder resources"""
        for encoder_name, encoder in self.encoders.items():
            encoder.cleanup()
        self.set_status(6102, "Rotary encoder manager torn down")


class EncoderHandler:
    """
    Handles a single rotary encoder with clock, data, and optional button pins.
    Detects rotation and button presses, and publishes events through the manager.
    """

    def __init__(self, name, clk_pin, dt_pin, btn_pin=None, manager=None):
        self.name = name
        self.manager = manager
        self.clk_pin = clk_pin
        self.dt_pin = dt_pin
        self.btn_pin = btn_pin

        # Setup GPIO pins
        self.clk = machine.Pin(clk_pin, machine.Pin.IN)
        self.dt = machine.Pin(dt_pin, machine.Pin.IN)
        self.btn = machine.Pin(btn_pin, machine.Pin.IN) if btn_pin is not None else None

        # Track state
        self.last_clk_state = self.clk.value()
        self.last_dt_state = self.dt.value()
        self.last_btn_state = self.btn.value() if self.btn else 1  # Button inactive (high) by default
        self.connected = False
        self.clicks_pending = 0

        # Debounce timing
        self.last_change_time = time.ticks_ms()
        self.debounce_ms = 5

    def update(self, manager):
        """Called on each update cycle to check encoder state and publish events"""
        current_time = time.ticks_ms()
        time_since_last = time.ticks_diff(current_time, self.last_change_time)

        # Skip if within debounce window
        if time_since_last < self.debounce_ms:
            return

        current_clk = self.clk.value()
        current_dt = self.dt.value()
        current_btn = self.btn.value() if self.btn else 1

        clk_changed = current_clk != self.last_clk_state
        dt_changed = current_dt != self.last_dt_state
        btn_changed = current_btn != self.last_btn_state

        # Publish encoder connected event on first detection
        if not self.connected:
            manager.publish_event(f"rotary_encoder.{self.name}_connected", {"encoder": self.name})
            self.connected = True

        # Detect rotation based on CLK falling edge
        if clk_changed and current_clk == 0:
            # CLK went from high to low (falling edge)
            if current_dt == 0:
                # Clockwise rotation
                manager.publish_event(f"rotary_encoder.{self.name}_moved_clockwise", {
                    "encoder": self.name,
                    "clicks": 1
                })
            else:
                # Counter-clockwise rotation
                manager.publish_event(f"rotary_encoder.{self.name}_moved_anticlockwise", {
                    "encoder": self.name,
                    "clicks": 1
                })
            self.last_change_time = current_time

        # Detect button press (active low)
        if btn_changed and current_btn == 0 and self.btn:
            # Button pressed (went low)
            manager.publish_event(f"rotary_encoder.{self.name}_button_pressed", {
                "encoder": self.name,
                "state": "pressed"
            })
            self.last_change_time = current_time

        # Update state
        self.last_clk_state = current_clk
        self.last_dt_state = current_dt
        self.last_btn_state = current_btn

    def cleanup(self):
        """Clean up GPIO resources"""
        # MicroPython Pin objects don't require explicit cleanup
        pass
