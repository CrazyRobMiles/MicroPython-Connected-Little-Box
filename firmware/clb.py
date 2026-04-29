import os
import json
import sys
import select
import time
import machine
from app_manifest import APPS

class CLB:

    version = "2.0.0"


    def __init__(self, config):

        self.config = config
        self.settings = config.settings

        self.manager_entries = []
        self.status = {}
        self.interface = {}
        self._input_buffer = ""
        self.running=True

    def _load_managers(self):

        entries = []

        # Load only managers that are specified in settings.json
        for manager_name, manager_config in self.settings.items():

            print(f"Checking manager: {manager_name}")

            # Only load if enabled
            if not manager_config.get("enabled", False):
                print(f"[CLB] Skipping disabled manager: {manager_name}")
                continue

            # Construct the module name
            module_name = f"{manager_name}_manager"
            full_name = f"managers.{module_name}"

            print(f"Loading: {full_name}")
            try:
                module = __import__(full_name)
                for part in full_name.split(".")[1:]:
                    module = getattr(module, part)
                manager_class = getattr(module, "Manager")
                manager_instance = manager_class(self)

                entries.append((manager_name, manager_instance))
            except Exception as e:
                sys.print_exception(e)
                print(f"Failed to load {module_name}: {e}")
                # Don't create defaults, just don't have this manager
                continue

        return entries

    def _resolve_dependencies(self, manager_lookup):
        """
        Resolve dependencies and remove managers whose dependencies are disabled.
        This is called recursively until no more managers are removed.
        Returns the filtered list of managers that should be kept.
        """
        changed = True
        while changed:
            changed = False
            managers_to_remove = []
            for name, mgr in manager_lookup.items():
                if not mgr.enabled:
                    continue
                # Check if all dependencies are available and enabled
                deps = mgr.get_dependencies()
                for dep_name in deps:
                    if dep_name not in manager_lookup:
                        print(f"[CLB] Removing manager '{name}' because dependency '{dep_name}' is not loaded")
                        managers_to_remove.append(name)
                        changed = True
                        break
                    elif not manager_lookup[dep_name].enabled:
                        print(f"[CLB] Removing manager '{name}' because dependency '{dep_name}' is disabled")
                        managers_to_remove.append(name)
                        changed = True
                        break
            
            # Remove managers from lookup
            for name in managers_to_remove:
                del manager_lookup[name]

    def setup(self):

        self.manager_entries = self._load_managers()

        manager_lookup = {name: mgr for name, mgr in self.manager_entries}

        for name, mgr in self.manager_entries:
            defaults = mgr.get_defaults()
            saved = self.settings.get(name, {})
            merged = defaults.copy()
            merged.update(saved)      # saved values override defaults
            mgr.settings = merged
            mgr.enabled = merged.get("enabled", True)
            # keep CLB's settings dict in sync
            self.settings[name] = merged

        # Resolve dependencies and remove managers with missing/disabled dependencies
        self._resolve_dependencies(manager_lookup)

        # Update manager_entries to only include managers that passed dependency check
        self.manager_entries = [(name, mgr) for name, mgr in self.manager_entries if name in manager_lookup]

        for name, mgr in self.manager_entries:
            deps = mgr.get_dependencies()
            mgr.dependency_instances = [manager_lookup[d] for d in deps if d in manager_lookup]

        from managers.base_manager import console_printer

        # Call setup() for enabled managers only
        for name, mgr in self.manager_entries:
            mgr.add_message_handler(console_printer)
            if not mgr.enabled:
                mgr.state = "disabled"
                continue
            try:
                mgr.setup(mgr.settings)
            except Exception as e:
                print(f"[CLB] Manager {name} crashed during setup:")
                sys.print_exception(e)
                mgr.state = "error"
                mgr.enabled = False
            self.status[name] = mgr.get_status()

        self.build_interface()

        for name, mgr in self.manager_entries:
            try:
                mgr.setup_services()
            except Exception as e:
                print(f"[CLB] Error in {name}.setup_services(): {e}")
                sys.print_exception(e)

    def list_events(self):
        """
        Return a dictionary of all published events from all managers.

        Expected output format:
        {
            "clock": [
                "clock.minute — Emitted when the minute changes",
                "clock.hour   — Emitted when the hour changes"
            ],
            "wifi": [
                "wifi.connected — WiFi has connected"
            ]
        }
        """
        events = {}

        for name, mgr in self.manager_entries:
            if not mgr.enabled:
                continue

            if not hasattr(mgr, "get_published_events"):
                continue

            try:
                published = mgr.get_published_events()
            except Exception as e:
                print(f"[CLB] Error reading events from manager '{name}': {e}")
                continue

            if not published:
                continue

            formatted = []
            for entry in published:
                # Support both old-style (strings) and new-style (dicts)
                if isinstance(entry, dict):
                    evt = entry.get("name", "")
                    desc = entry.get("description", "")
                    if desc:
                        formatted.append(f"{evt} — {desc}")
                    else:
                        formatted.append(evt)
                else:
                    # fallback if someone returns just a string
                    formatted.append(str(entry))

            if formatted:
                events[name] = formatted

        return events
    
    def command_list_events(self):
        ev = self.list_events()
        print("\nPublished Events:")
        for mgr, lst in ev.items():
            print(f"[{mgr}]")
            for e in lst:
                print(f"  {e}")
        print()
    
   
    def get_interface(self):
        return {
            "events": ("List all events published by managers", self.command_list_events),                    
            "set": ("Set setting value", self.set_setting),
            "status": ("Show manager status", self.describe),
            "reset": ("Reset settings to defaults", self.reset),
            "settings": ("Display all current settings", self.show_settings),
            "teardown": ("Tear down all managers and release resources", self.teardown),
            "stop": ("Stop main loop (sets running=False)", self.stop),
            "help": ("Show available commands (optional prefix)", self.show_help),
            "rebuild-iface": ("Rebuild unified interface registry", self.build_interface),
            "events": ("List all events and subscribers", self.command_list_events),
            "memory": ("Show memory status",self.show_memory_status),
            "exec": ("Executes Python statement", self.execute_python_statement),
            "apps": ("Lists all the applications", self.show_applications),
            "select-app" : ("Select an application for this device",self.select_application)
        }

    def update(self):
        for name, mgr in self.manager_entries:
            start_time = time.ticks_ms()
            mgr.update()
            now = time.ticks_ms()
            update_time_ms = time.ticks_diff(now,start_time)
            mgr.update_time_ms=update_time_ms
            mgr.total_time_ms=mgr.total_time_ms+update_time_ms
            self.status[name] = mgr.get_status()

    def update_console(self):
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            char = sys.stdin.read(1)
            if char == '\n':
                sys.stdout.write("\r\x1b[K")
                print(f"{self._input_buffer}\n")
                self.handle_command(self._input_buffer.strip())
                self._input_buffer = ""
            else:
                self._input_buffer += char

    def reset(self):
        if any(getattr(mgr, "state", "") == "error" for _, mgr in self.manager_entries):
            print("One or more managers failed setup — refusing to reset to defaults.")
            return

        try:
            with open(self.settings_file, "w") as f:
                json.dump(
                    {name: mgr.get_defaults() for name, mgr in self.manager_entries},
                    f
                )
            print("Settings reset to defaults.")
        except Exception as e:
            print("Error resetting settings:", e)

    def teardown(self):
        for name, mgr in self.manager_entries:
            if hasattr(mgr, "teardown"):
                try:
                    mgr.teardown()
                    print(f"Torn down manager: {name}")
                except Exception as e:
                    print(f"Error tearing down manager {name}: {e}")

    def stop(self):
        print("Stopping the box")
        self.teardown()
        self.running=False

    def get_versions(self):
        return {
            name: {
                "version": mgr.get_version(),
                "dependencies": mgr.get_dependencies()
            }
            for name, mgr in self.manager_entries
        }

    def describe(self):
        print(f"\nConnected Little Box Version {self.version} Status Report")
        for name, mgr in self.manager_entries:
            print(f"{name:<10} v{mgr.get_version():<8} state: {mgr.state:<16} update time: {mgr.update_time_ms}: total time: {mgr.total_time_ms} enabled: {mgr.enabled}  deps: {mgr.get_dependencies()}")

    def show_help(self, prefix=None):
        """
        Display all available commands/services from enabled managers.
        Optionally filter by prefix, e.g. 'help pixel' shows only pixel commands.
        """
        if not hasattr(self, "interface") or not self.interface:
            print("No commands available. Try 'rebuild-iface' if managers have changed.")
            return

        if prefix:
            prefix = prefix.lower().rstrip(".")
            entries = {n: e for n, e in self.interface.items() if n.startswith(prefix + ".")}
            if not entries:
                print(f"No commands found for '{prefix}'")
                return
            print(f"\nAvailable commands for '{prefix}':")
        else:
            entries = self.interface
            print("\nAvailable Commands and Services:")

        by_manager = {}
        for name, entry in entries.items():
            manager = entry.get("manager", name.split(".")[0])
            by_manager.setdefault(manager, []).append((name, entry))

        for mgr_name, items in sorted(by_manager.items()):
            print(f"\n[{mgr_name}]")
            for name, entry in sorted(items):
                desc = entry.get("description", "")
                print(f"  {name:<24} - {desc}")
        print()


    def handle_command(self, line: str):
        """Parse and invoke a command using Python function-call syntax.
        Examples:
            pixel.fill(255, 0, 0)
            pixel.mode("wordsearch")
            pixel.fill(red=255, green=0, blue=0)
            help("pixel")
            status()
            help
        A bare name with no parentheses is treated as a zero-argument call.
        """
        if not line:
            return
        line = line.strip()
        if not line:
            return

        # set uses its own parser: set manager.setting=value (no parens needed)
        if line.startswith("set ") and "(" not in line:
            self.set_setting(line[4:].strip())
            return

        paren_pos = line.find("(")
        if paren_pos != -1:
            if not line.endswith(")"):
                print("Syntax error: missing closing ')'")
                return
            cmd = line[:paren_pos].strip()
            args_str = line[paren_pos + 1:-1]
        else:
            cmd = line
            args_str = None

        entry = self.interface.get(cmd)
        if not entry:
            print(f"Unknown command: '{cmd}'. Try help().")
            return

        func = entry["handler"]

        try:
            if args_str is not None and args_str.strip():
                result = eval(f"_f_({args_str})", {"_f_": func})
            else:
                result = func()
            if result is not None:
                print(result)
        except TypeError as e:
            desc = entry.get("description", "")
            print(f"Usage error for '{cmd}': {e}")
            if desc:
                print(f"  {cmd} - {desc}")
        except Exception as e:
            sys.print_exception(e)
            print(f"Error running '{cmd}': {e}")

    def notify_manager_setting_changed(self, manager_name, setting_name, old_value,new_value):
        """
        Find the manager instance for manager_name and call its on_setting_changed()
        method if present.
        """
        for name, mgr in self.manager_entries:
            if name == manager_name:
                # Manager found — does it implement the callback?
                cb = getattr(mgr, "on_setting_changed", None)
                if cb:
                    try:
                        cb(setting_name, old_value,new_value)
                    except Exception as e:
                        print(f"[CLB] Error in {manager_name}.on_setting_changed: {e}")
                return  # Manager found, exit function

        print(f"[CLB] notify_manager_setting_changed: no manager called '{manager_name}'")

    def _apply_dotted_path(self, obj, path, value):
        """
        Apply assignment inside a nested structure.
        Supports dictionary keys and key[index] list access.
        """
        steps = path.split(".")
        node = obj

        # Walk down to the parent of the target
        for step in steps[:-1]:
            key, idx = self._parse_path_step(step)

            if not isinstance(node, dict):
                raise TypeError(f"Cannot traverse key '{key}' on non-dict container")

            if key not in node:
                raise KeyError(f"Key '{key}' not found")

            node = node[key]

            # Apply list indexing
            if idx is not None:
                if not isinstance(node, list):
                    raise TypeError(f"'{key}' is not a list but index was used")
                if idx < 0 or idx >= len(node):
                    raise IndexError(f"Index {idx} out of range for list '{key}'")
                node = node[idx]

        # Now apply final write
        final_step = steps[-1]
        key, idx = self._parse_path_step(final_step)

        if key not in node:
            raise KeyError(f"Key '{key}' not found in final container")

        container = node[key]

        if idx is None:
            # Simple dict write
            node[key] = value
        else:
            # List index write
            if not isinstance(container, list):
                raise TypeError(f"Cannot index into non-list '{key}'")
            if idx < 0 or idx >= len(container):
                raise IndexError(f"Index {idx} out of range for list '{key}'")
            container[idx] = value

    def _parse_path_step(self, step):
        """
        Parse a single dotted path step.
        Supports:
            key
            key[index]
        Returns (key, index) where index may be None.
        """
        if "[" in step and step.endswith("]"):
            key, idx = step[:-1].split("[", 1)
            return key, int(idx)
        return step, None

    def _get_nested_value(self, obj, path):
        """
        Walk a nested structure (dicts and lists) using dotted path syntax.
        Array indices must be explicit: key[index].
        Example:
            motors.motor0.pins[2]
        """
        node = obj
        steps = path.split(".")

        for step in steps:
            key, idx = self._parse_path_step(step)

            if not isinstance(node, dict):
                raise TypeError(f"Cannot use key '{key}' on non-dict container")

            if key not in node:
                raise KeyError(f"Key '{key}' not found")

            node = node[key]

            if idx is not None:
                if not isinstance(node, list):
                    raise TypeError(f"Key '{key}' is not a list, but index used")
                if idx < 0 or idx >= len(node):
                    raise IndexError(f"Index {idx} out of range for list under '{key}'")
                node = node[idx]

        return node

    def set_setting(self, *args):
        """
        Set a setting value using:
            set manager.setting.path=value

        Supports nested dictionaries and explicit list indexing using [n].
        Notifies manager via on_setting_changed(path, old, new).
        """
        # ----------------------------------------------------
        # 1. Basic syntax check
        # ----------------------------------------------------
        if len(args) != 1 or "=" not in args[0]:
            print("Usage: set manager.setting=value")
            return

        setting_expr = args[0]
        key_part, value_str = setting_expr.split("=", 1)

        # ----------------------------------------------------
        # 2. Extract manager and dotted-path setting
        # ----------------------------------------------------
        if "." not in key_part:
            print("Invalid format. Use manager.setting=value")
            return

        manager_name, setting_path = key_part.split(".", 1)

        # Validate manager
        if manager_name not in self.settings:
            print(f"Unknown manager: {manager_name}")
            return

        settings_dict = self.settings[manager_name]

        # ----------------------------------------------------
        # 3. Retrieve existing value (leaf) to determine type
        # ----------------------------------------------------
        try:
            # Nested path or list-indexed path?
            if "." in setting_path or "[" in setting_path:
                original_value = self._get_nested_value(settings_dict, setting_path)
            else:
                # Simple key
                original_value = settings_dict[setting_path]
        except Exception as e:
            print(f"Invalid setting path '{setting_path}': {e}")
            return

        # ----------------------------------------------------
        # 4. Coerce the new value based on existing type
        # ----------------------------------------------------
        raw = value_str
        try:
            if isinstance(original_value, bool):
                new_value = raw.lower() in ("true", "1", "yes", "on")

            elif isinstance(original_value, int):
                new_value = int(raw)

            elif isinstance(original_value, float):
                new_value = float(raw)

            elif isinstance(original_value, (list, dict)):
                import json
                new_value = json.loads(raw)

            else:
                # Fallback: treat as string
                new_value = raw

        except Exception as e:
            print(f"Failed to convert value '{raw}': {e}")
            return

        # ----------------------------------------------------
        # 5. Apply update to nested structure
        # ----------------------------------------------------
        try:
            if "." in setting_path or "[" in setting_path:
                self._apply_dotted_path(settings_dict, setting_path, new_value)
            else:
                print(f"Simple setting:{setting_path} {new_value}")
                settings_dict[setting_path] = new_value
        except Exception as e:
            print(f"Failed to update setting '{setting_path}': {e}")
            return

        print(f"{manager_name}.{setting_path} updated to {new_value}")

        # ----------------------------------------------------
        # 6. Save device settings
        # ----------------------------------------------------
        try:
            self.config.save()
        except Exception as e:
            print(f"Warning: could not save settings file: {e}")

        # ----------------------------------------------------
        # 7. Notify manager (if implemented)
        # ----------------------------------------------------
        mgr = None
        for name, instance in self.manager_entries:
            if name == manager_name:
                mgr = instance
                break

        if mgr and hasattr(mgr, "on_setting_changed"):
            try:
                mgr.on_setting_changed(setting_path, original_value, new_value)
            except Exception as e:
                print(f"[CLB] Manager '{manager_name}' on_setting_changed failed: {e}")

    def show_settings(self):
        print("\nCurrent Settings:")
        for manager_name, settings in self.settings.items():
            print(f"[{manager_name}]")
            for key, val in settings.items():
                print(f"  {key:<12}: {val} ({type(val).__name__})")

    def build_interface(self):
        self.interface = {}

        for cmd, (desc, func) in self.get_interface().items():
            self.interface[cmd] = {
                "handler": func,
                "description": desc,
                "manager": "clb"
            }   

        for name, mgr in self.manager_entries:
            if not mgr.enabled:
                continue
            iface = mgr.get_interface()
            for cmd_name, (desc, func) in iface.items():
                full_name = f"{mgr.name}.{cmd_name}"
                self.interface[full_name] = {
                    "handler": func,
                    "description": desc,
                    "manager": mgr.name
                }
        print(f"[CLB] Built unified interface with {len(self.interface)} commands/services")

    def execute_python_statement(self,statement):
        print(f"Executing: {statement}")
        exec(statement)

    def show_applications(self):
        print("Applications Available:")
        for app in APPS:
            name=app["name"]
            desc=app["desc"]
            print(f"   {name} - {desc}")
            
    def find_app_by_prefix(self,items, key):
        return next((item for item in items if item["name"].startswith(key)), None)            
    
    def get_manager_class(self, manager_name):
        module_name = f"managers.{manager_name}_manager"

        module = __import__(module_name)
        for part in module_name.split(".")[1:]:
            module = getattr(module, part)

        return getattr(module, "Manager")

    def configure_app_settings(self, app):
        name=app["name"]
        desc=app["desc"]
        file=app["file"]
        
        print(f"Configuring: {name} - {desc}")
        ok = input("Configuring this will erase any existing settings. Enter Y to continue, N to abandon: ")
        if ok == "Y":
            print("Performing configuration selection")
            mgr = self.get_manager_class(file)
            defaults = mgr.app_default_settings
            print(defaults)
            self.config.settings = defaults
            self.settings = defaults
            self.config.save()
            print("Configuration updated")
            print("Device will reset in five seconds")
            for i in range(5):
                print(f"....{i}")
                time.sleep(1)
            print("Reset")
            machine.reset()
        else:
            print("Configuration abandoned")
    
    def select_application(self):
        self.show_applications()
        name= input ("Enter the name of the app:")
        app = self.find_app_by_prefix(APPS,name)
        if app==None:
            print(f"Name {name} not found")
        else:
            self.configure_app_settings(app)
        
    def call(self, name, *args):
        """Invoke a command/service by name."""
        entry = self.interface.get(name)
        if not entry:
            raise ValueError(f"Unknown command/service: {name}")
        return entry["handler"](*args)

    def get_handle(self, name):
        """Return callable handler for caching."""
        entry = self.interface.get(name)
        if not entry:
            raise ValueError(f"Unknown command/service: {name}")
        return entry["handler"]
    
    def get_event(self, event_name):
        """
        Locate an event owned by any manager.
        Returns an Event object or None.
        """
        for _, mgr in self.manager_entries:
            if hasattr(mgr, "events") and event_name in mgr.events:
                return mgr.events[event_name]
        return None

    def list_events(self):
        """
        Return a dictionary:
            manager → [{name, description, subscribers}]
        """
        out = {}
        for name, mgr in self.manager_entries:
            if hasattr(mgr, "events"):
                lst = []
                for evt in mgr.events.values():
                    lst.append({
                        "name": evt.name,
                        "description": evt.description,
                        "subscribers": len(evt.subscribers)
                    })
                if lst:
                    out[name] = lst
        return out


    def command_list_events(self):
        evmap = self.list_events()
        print("\nAvailable Events:")
        print("-----------------")
        for mgr, events in evmap.items():
            print(f"[{mgr}]")
            for e in events:
                print(f"  {e['name']:<18} - {e['description']}  ({e['subscribers']} subscribers)")
        print()
        
    def show_memory_status(self):
        import gc
        import micropython

        gc.collect()

        free = gc.mem_free()
        alloc = gc.mem_alloc()
        total = free + alloc

        print("[Memory]")
        print(f"  Total heap : {total} bytes")
        print(f"  Used       : {alloc} bytes")
        print(f"  Free       : {free} bytes")

        # Fragmentation insight (Micropython-specific)
        try:
            print(f"  Largest free block : {micropython.mem_info(0) or 'see above'}")
        except Exception:
            pass

