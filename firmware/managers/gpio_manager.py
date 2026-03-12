from managers.base_manager import CLBManager
from managers.event import Event
import machine
import time

class Manager(CLBManager):
    version = "1.0.0"

    def __init__(self, clb):
        super().__init__(clb, defaults={
            "input_pins": [],
            "output_pins": [],
            "default_debounce_ms": 20,
            "pullup":False
        })
        self.input_pins = {}      # {pin_name: {'pin': Pin, 'last_state': bool, 'last_change_time': int, 'debounce_ms': int}}
        self.output_pins = {}     # {pin_name: {'pin': Pin, 'initial_state': int}}
        self.events = {}    # {event_name: Event object}

    def setup(self, settings):
        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        default_debounce_ms = self.settings.get("default_debounce_ms", 20)

        # Setup input pins from configuration
        input_pins_config = self.settings.get("input_pins", [])
        for pin_config in input_pins_config:
            print(pin_config)
            self._configure_input_pin(pin_config, default_debounce_ms)

        # Setup output pins from configuration
        output_pins_config = self.settings.get("output_pins", [])
        for pin_config in output_pins_config:
            self._configure_output_pin(pin_config)

        self.state = self.STATE_OK
        self.set_status(6001, "GPIO manager ready")

    def _create_gpio_events(self, GPIO_name):
        """Create events for GPIO"""
        
        event_names = [
            f"gpio.{GPIO_name}_low",
            f"gpio.{GPIO_name}_high"
        ]

        for event_name in event_names:
            if event_name not in self.events:
                self.events[event_name] = Event(
                    name=event_name,
                    description=f"GPIO '{GPIO_name}' event: {event_name.split('_', 1)[1]}",
                    owner=self
                )

    def _configure_input_pin(self, pin_config, default_debounce_ms):
        """Configure an input pin from a config dict"""
        if isinstance(pin_config, dict):
            pin_name = pin_config.get("name")
            pin_number = pin_config.get("pin")
            debounce_ms = pin_config.get("debounce_ms", default_debounce_ms)
            pullup = pin_config.get("pullup", False)
            self._create_gpio_events(pin_name)
        else:
            print(f"[GPIO] Invalid input pin config: {pin_config}")
            return

        if not pin_name or pin_number is None:
            print(f"[GPIO] Input pin config missing name or pin number")
            return

        try:
            if pullup:
                pin = machine.Pin(pin_number, machine.Pin.IN, machine.Pin.PULL_UP)
            else:
                pin = machine.Pin(pin_number, machine.Pin.IN)
            self.input_pins[pin_name] = {
                'pin': pin,
                'pin_number': pin_number,
                'last_state': pin.value(),
                'last_change_time': time.ticks_ms(),
                'pullup':pullup,
                'debounce_ms': debounce_ms
            }
            print(f"[GPIO] Configured input pin '{pin_name}' on GPIO {pin_number} (debounce: {debounce_ms}ms)")
        except Exception as e:
            print(f"[GPIO] Failed to configure input pin '{pin_name}' on GPIO {pin_number}: {e}")

    def _configure_output_pin(self, pin_config):
        """Configure an output pin from a config dict"""
        if isinstance(pin_config, dict):
            pin_name = pin_config.get("name")
            pin_number = pin_config.get("pin")
            initial_state = pin_config.get("initial_state", 0)
        else:
            print(f"[GPIO] Invalid output pin config: {pin_config}")
            return

        if not pin_name or pin_number is None:
            print(f"[GPIO] Output pin config missing name or pin number")
            return

        try:
            pin = machine.Pin(pin_number, machine.Pin.OUT)
            pin.value(initial_state)
            self.output_pins[pin_name] = {
                'pin': pin,
                'pin_number': pin_number,
                'initial_state': initial_state
            }
            print(f"[GPIO] Configured output pin '{pin_name}' on GPIO {pin_number} (initial: {initial_state})")
        except Exception as e:
            print(f"[GPIO] Failed to configure output pin '{pin_name}' on GPIO {pin_number}: {e}")

    def setup_services(self):
        """Connect to event manager to publish GPIO events"""
        self.event_manager = self.get_service_handle("event")
        if self.event_manager:
            print("[GPIO] Connected to event service")
        else:
            print("[GPIO] Event service unavailable")

    def update(self):
        """Monitor input pins for state changes and publish events"""
        now = time.ticks_ms()

        for pin_name, pin_info in self.input_pins.items():
            
            current_state = pin_info['pin'].value()
            last_state = pin_info['last_state']
            
            # Do nothing if the states are the same
            if current_state == last_state:
                # Keep track of our last steady state
                pin_info['last_change_time'] = now
            else:
                # Different
                time_since_change = time.ticks_diff(now, pin_info['last_change_time'])

                if time_since_change > pin_info['debounce_ms']:
                    # long pulse
                    pin_info['last_state'] = current_state
                    pin_info['last_change_time'] = now
                    # Publish event for transition
                    if current_state:
                        event_name = f"gpio.{pin_name}_high"
                        print(f"[GPIO] Event: {event_name}")
                        self.events[event_name].publish("boo")
                    else:
                        event_name = f"gpio.{pin_name}_low"
                        print(f"[GPIO] Event: {event_name}")
                        self.events[event_name].publish({"pin": pin_name, "transition": "high_to_low"})

    def get_interface(self):
        return {
            "set": ("set <pin_name> <state>", self.command_set_pin),
            "get": ("get <pin_name>", self.command_get_pin),
            "list": ("list pins", self.command_list_pins),
        }

    def command_set_pin(self, pin_name, state=""):
        """Set an output pin to high (1) or low (0)"""
        if pin_name not in self.output_pins:
            print(f"[GPIO] Output pin '{pin_name}' not found")
            return

        try:
            state_value = int(state) if state else 0
            self.output_pins[pin_name]['pin'].value(state_value)
            print(f"[GPIO] Set output pin '{pin_name}' to {state_value}")
        except Exception as e:
            print(f"[GPIO] Failed to set pin '{pin_name}': {e}")

    def command_get_pin(self, pin_name):
        """Get the current state of an input or output pin"""
        if pin_name in self.input_pins:
            state = self.input_pins[pin_name]['last_state']
            print(f"[GPIO] Input pin '{pin_name}' state: {state}")
        elif pin_name in self.output_pins:
            state = self.output_pins[pin_name]['pin'].value()
            print(f"[GPIO] Output pin '{pin_name}' state: {state}")
        else:
            print(f"[GPIO] Pin '{pin_name}' not found")

    def command_list_pins(self):
        """List all configured pins"""
        print("[GPIO] Input pins:")
        if not self.input_pins:
            print("  (none)")
        for pin_name, pin_info in self.input_pins.items():
            state = pin_info['last_state']
            debounce = pin_info['debounce_ms']
            pullup = pin_info['pullup']
            print(f"  {pin_name} (GPIO {pin_info['pin_number']}, pullup {pullup} debounce {debounce}ms): {state}")

        print("[GPIO] Output pins:")
        if not self.output_pins:
            print("  (none)")
        for pin_name, pin_info in self.output_pins.items():
            state = pin_info['pin'].value()
            print(f"  {pin_name} (GPIO {pin_info['pin_number']}): {state}")

    def get_published_events(self):
        """Return list of events this manager publishes"""
        events = []
        
        # Add input pin transition events
        for pin_name in self.input_pins.keys():
            events.append({
                "name": f"gpio.{pin_name}_high",
                "description": f"GPIO input '{pin_name}' transitioned low to high"
            })
            events.append({
                "name": f"gpio.{pin_name}_low",
                "description": f"GPIO input '{pin_name}' transitioned high to low"
            })
        
        return events

    def teardown(self):
        """Clean up GPIO resources"""
        for pin_info in self.input_pins.values():
            try:
                pin_info['pin'].close()
            except:
                pass
        
        for pin_info in self.output_pins.values():
            try:
                pin_info['pin'].close()
            except:
                pass
        
        self.set_status(6002, "GPIO manager torn down")

