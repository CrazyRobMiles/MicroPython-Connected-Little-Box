
def console_printer(msg_id, msg_text):
    print(f"[{msg_id}] {msg_text}")

class CLBManager:
    version = "0.0.0"
    dependencies = []

    STATE_OK = "ok"
    STATE_STARTING = "starting"
    STATE_DISABLED = "disabled"
    STATE_ERROR = "error"
    STATE_WAITING = "waiting"

    def unresolved_dependencies(self):
        return [m for m in self.dependency_instances if not hasattr(m, 'state') or m.state != self.STATE_OK]
   
    def __init__(self, clb=None, defaults=None):
        self.clb = clb
        self.name = self.__class__.__module__.split('.')[-1].replace('_manager', '')
        self.defaults = defaults or {}
        self.settings = {}
        self.enabled = True
        self.state = self.STATE_STARTING
        self._status_text = "Not initialized"
        self._status_id = 0
        self._message_receivers = []
        self.update_time_ms = 0
        self.total_time_ms=0
        self.dependency_instances = []

    def get_interface(self):
        """
        Return a dictionary of exposed command/service entries.

        Example:
            return {
                "fill": ("fill <r> <g> <b>", self.fill_display),
                "clear": ("clear display", self.clear_display)
            }
        """
        return {}

    def setup_services(self):
        """Called after all managers are set up and the interface is built.
           Override in subclasses to connect to other services."""
        pass

    def get_defaults(self):
        d = self.defaults.copy()
        d["enabled"] = True
        return d

    def get_version(self):
        return self.__class__.version

    def get_dependencies(self):
        return self.__class__.dependencies

    def setup(self, settings_dict):
        merged = self.get_defaults()
        merged.update(settings_dict)
        self.settings = merged
        self.enabled = self.settings.get("enabled", False)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            self.set_status(1000, "Disabled by config")
        else:
            self.state = self.STATE_STARTING
            self.set_status(1001, "Starting...")

    def update(self):
        pass

    def get_status(self):
        return self._status_text

    def set_status(self, msg_id, msg_text):
        self._status_id = msg_id
        self._status_text = msg_text
        for handler in self._message_receivers:
            handler(msg_id, msg_text)

    def add_message_handler(self, handler):
        if handler not in self._message_receivers:
            self._message_receivers.append(handler)

    def remove_message_handler(self, handler):
        if handler in self._message_receivers:
            self._message_receivers.remove(handler)

    def get_service_handle(self, prefix, rebuild=True):
        """
        Return an object that exposes all functions under a given service prefix.

        Example:
            pixels = self.get_service_handle("pixel")
            pixels.fill(255, 0, 0)
            pixels.clear()

        Args:
            prefix (str): Manager/service prefix (e.g. "pixel")
            rebuild (bool): Rebuild interface if not yet ready.
        """
        if not self.clb:
            print(f"[{self.name}]No CLB reference available.")
            return None

        if rebuild and (not hasattr(self.clb, "interface") or not self.clb.interface):
            try:
                self.clb.build_interface()
            except Exception as e:
                print(f"[{self.name}]Failed to rebuild interface: {e}")

        # Collect all matching commands
        matches = {
            name[len(prefix) + 1:]: entry["handler"]
            for name, entry in self.clb.interface.items()
            if name.startswith(prefix + ".")
        }

        if not matches:
            print(f"[{self.name}]No service functions found for prefix '{prefix}'.")
            return None

        # Return as a lightweight proxy object for convenient dot access
        return _ServiceHandle(matches, prefix)
    # --- Yielding State Machine Support ---------------------------------------

    def change_state(self, fn, state_name=None, *args, **kwargs):
        """
        Replace the current yielding function (generator) with one from 'fn'.
        Automatically closes the previous one.
        Args:
            fn: a function returning a generator (i.e., one using yield)
            state_name: optional string for self.yield_state
            *args/**kwargs: arguments passed to fn when creating the generator
        """
        # Close old generator politely
        if hasattr(self, "_current") and self._current:
            try:
                self._current.close()
                print(f"[{self.name}] Closed previous state '{self.yield_state}'")
            except Exception:
                pass
            self._current = None

        # Create new generator
        try:
            self._current = fn(*args, **kwargs)
            self.yield_state = state_name or fn.__name__
            self.set_status(9999, f"State changed to {self.yield_state}")
            print(f"[{self.name}] Entered state '{self.yield_state}'")
        except Exception as e:
            self.yield_state = "error"
            self._current = None
            self.set_status(9998, f"Failed to enter state: {e}")
            print(f"[{self.name}] Failed to enter state: {e}")

    def update_yielding(self):
        """
        If a yielding function (generator) is active, advance it one step.
        Clears it when finished or if an error occurs.
        """
        if not hasattr(self, "_current") or not self._current:
            return

        try:
            next(self._current)
        except StopIteration:
            print(f"[{self.name}] State '{self.yield_state}' complete")
            self._current = None
            self.yield_state = "idle"
            self.set_status(9997, "Yielding function complete")
        except Exception as e:
            print(f"[{self.name}] Error in state '{self.yield_state}': {e}")
            self._current = None
            self.yield_state = "error"
            self.set_status(9996, f"Error in state: {e}")


class _ServiceHandle:
    """Lightweight proxy exposing service functions as attributes."""
    def __init__(self, funcs, prefix):
        self._funcs = funcs
        self._prefix = prefix

    def __getattr__(self, name):
        if name in self._funcs:
            return self._funcs[name]
        raise AttributeError(f"Service '{self._prefix}' has no function '{name}'")

    def list(self):
        """List available functions on this service handle."""
        return list(self._funcs.keys())

    def __repr__(self):
        funcs = ", ".join(self._funcs.keys())
        return f"<ServiceHandle '{self._prefix}' funcs=[{funcs}]>"

    def get_published_events(self):
        """
        Return events owned by this manager, if any.
        """
        if hasattr(self, "events"):
            return [
                {"name": evt.name, "description": evt.description}
                for evt in self.events.values()
            ]
        return []
