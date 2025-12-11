import os
import json
import sys
import select
import time

class CLB:

	version = "1.0.0"


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

		for file in os.listdir("/managers"):

			print(f"Found:{file}")

			if file.endswith("_manager.py") and not file.startswith("_"):
				module_name = file[:-3]
				full_name = f"managers.{module_name}"
				manager_name = module_name[:-8]  # strip '_manager'

				# Decide if this manager should be loaded at all
				saved_for_mgr = self.settings.get(manager_name, {})
				enabled = saved_for_mgr.get("enabled", True)
				if not enabled:
					print(f"[CLB] Skipping disabled manager: {manager_name}")
					continue  # <-- do not import / instantiate

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

		for name, mgr in self.manager_entries:
			deps = mgr.get_dependencies()
			mgr.dependency_instances = [manager_lookup[d] for d in deps if d in manager_lookup]

		from managers.base import console_printer

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
			"events": ("List all events and subscribers", self.command_list_events)
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
		"""Parse a console line and invoke a unified-interface command.
		Examples:
			pixel.fill 255 0 0
			pixel.mode "wordsearch"
			wordsearch.load '{"grid": "..."}'
			stepper.move 100 -50  # ints
			net.set-host 0xC0A80164  # hex -> 3232235876
			flag.set true            # bool
		"""
		if not line:
			return

		line = line.strip()
		if not line:
			return

		parts = self._split_args(line)
		if not parts:
			return

		cmd, *raw_args = parts

		# built-in: help (uses unified interface too)
		if cmd == "help":
			self.show_help(raw_args[0] if raw_args else None)
			return

		entry = self.interface.get(cmd)
		if not entry:
			print(f"Unknown command: {cmd}. Try 'help'.")
			return

		func = entry["handler"]

		# Best-effort coercion of string args to useful Python types
		args = []
		for a in raw_args:
			args.append(self._coerce_arg(a))

		try:
			result = func(*args)
			if result is not None:
				print(result)
		except TypeError as e:
			desc = entry.get("description", "")
			print(f"Usage error for {cmd}: {e}")
			if desc:
				print(f"Hint: {cmd} - {desc}")
		except Exception as e:
			sys.print_exception(e)
			print(f"Error running {cmd}: {e}")

	def _split_args(self, s: str):
		"""
		Split a command line into arguments, preserving quotes so _coerce_arg()
		can tell whether a token was originally quoted.
		"""
		out, buf, quote = [], [], None
		i, n = 0, len(s)

		while i < n:
			c = s[i]

			if quote:
				if c == quote:
					buf.append(c)     # keep closing quote
					quote = None
				elif c == "\\" and i+1 < n and s[i+1] in ('"', "'", "\\"):
					buf.append(s[i+1])
					i += 1
				else:
					buf.append(c)
			else:
				if c in ("'", '"'):
					quote = c
					buf.append(c)     # keep opening quote
				elif c.isspace():
					if buf:
						out.append("".join(buf))
						buf = []
				else:
					buf.append(c)

			i += 1

		# Final token
		if buf:
			out.append("".join(buf))

		return out

	def _coerce_arg(self, a: str):
		"""Turn console strings into useful Python values, preserving quoted text."""
		if not a:
			return a

		# QUOTED STRINGS — always return raw string without the quotes
		if (a.startswith('"') and a.endswith('"')) or (a.startswith("'") and a.endswith("'")):
			return a[1:-1]

		low = a.lower()

		# JSON objects/arrays
		if (a.startswith("{") and a.endswith("}")) or (a.startswith("[") and a.endswith("]")):
			try:
				import ujson as json
			except Exception:
				import json
			try:
				return json.loads(a)
			except Exception:
				pass

		# Booleans / null
		if low in ("true", "false"):
			return low == "true"
		if low in ("none", "null"):
			return None

		# Hex ints like 0xFFEE
		if a.startswith(("0x", "0X")):
			try:
				return int(a, 16)
			except Exception:
				pass

		# Int
		if all(ch.isdigit() or ch in "+-" for ch in a):
			try:
				return int(a)
			except Exception:
				pass

		# Float
		if "." in a and all(ch in "0123456789+-.eE" for ch in a):
			try:
				return float(a)
			except Exception:
				pass

		# Tuple shorthand: "(1,2,3)"
		if a.startswith("(") and a.endswith(")"):
			inner = a[1:-1].strip()
			if inner == "":
				return tuple()
			return tuple(self._coerce_arg(x.strip()) for x in inner.split(","))

		# Comma list shorthand: "1,2,3"
		if "," in a and (" " not in a):
			return [self._coerce_arg(x) for x in a.split(",")]

		# Fallback: raw string
		return a

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
				print("mgr found*****************************")
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
