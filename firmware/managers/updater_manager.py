# updater_manager.py
#
# Auto-update framework for Connected Little Box (CLB)
#
# This version supports:
#   ✓ Manifest-driven updates
#   ✓ Updating ANY .py file (not just managers)
#   ✓ New file installation
#   ✓ SHA-based update detection
#   ✓ User-visible version text
#   ✓ Automatic restart
#
# Expected manifest.json format:
#
# {
#   "files": {
#       "clb.py": {
#         "version": "1.0.0",
#         "sha": "abcdef1234...",
#         "url": "https://raw.githubusercontent.com/.../clb.py"
#       },
#       "managers/base.py": {
#         "version": "1.0.0",
#         "sha": "...",
#         "url": "..."
#       }
#   }
# }

from managers.base import CLBManager
import time, sys, os

try:
    import ujson as json
except ImportError:
    import json

try:
    import urequests as requests
except ImportError:
    import requests


class Manager(CLBManager):
    version = "2.0.0"
    dependencies = ["wifi"]

    STATE_IDLE = "idle"
    STATE_CHECKING = "checking"
    STATE_UPDATING = "updating"
    STATE_ERROR = "error"

    def __init__(self, clb):
        super().__init__(clb, defaults={
            "enabled": True,
            "manifest_url": "https://raw.githubusercontent.com/CrazyRobMiles/MicroPython-Connected-Little-Box/main/manifest.json",
            "check_interval_minutes": 120,
            "auto_restart": True
        })
        self.state = self.STATE_IDLE
        self.next_check_ms = 0
        self.pending_restart = False

    # ----------------------------------------------------------------------
    # Setup
    # ----------------------------------------------------------------------

    def setup(self, settings):
        super().setup(settings)
        if not self.enabled:
            self.state = "disabled"
            return

        self.state = self.STATE_IDLE
        self.next_check_ms = time.ticks_ms()  # perform initial check ASAP
        self.set_status(9000, "Updater ready (SHA-based mode)")

    # ----------------------------------------------------------------------
    # Main update loop
    # ----------------------------------------------------------------------

    def update(self):
        if not self.enabled:
            return

        if self.pending_restart:
            time.sleep(0.5)
            self._restart_system()
            return

        if self.state == self.STATE_IDLE:
            if time.ticks_diff(time.ticks_ms(), self.next_check_ms) >= 0:
                self._check_for_updates()

    # ----------------------------------------------------------------------
    # Manifest Fetch + Compare + Update
    # ----------------------------------------------------------------------

    def _check_for_updates(self):
        self.state = self.STATE_CHECKING
        url = self.settings["manifest_url"]
        self.set_status(9001, f"Fetching manifest: {url}")

        try:
            r = requests.get(url)
            if r.status_code != 200:
                raise OSError(f"HTTP {r.status_code}")
            manifest = r.json()
        except Exception as e:
            self.state = self.STATE_ERROR
            self.set_status(9002, f"Manifest fetch failed: {e}")
            self._schedule_next()
            return

        if "files" not in manifest:
            self.state = self.STATE_ERROR
            self.set_status(9003, "Manifest missing 'files' section")
            self._schedule_next()
            return

        updates = self._compare_with_local_shas(manifest["files"])
        if updates:
            self._perform_updates(updates)
        else:
            self.set_status(9004, "All files up to date")
            self.state = self.STATE_IDLE
            self._schedule_next()

    def _schedule_next(self):
        mins = int(self.settings["check_interval_minutes"])
        self.next_check_ms = time.ticks_add(time.ticks_ms(), mins * 60_000)

    # ----------------------------------------------------------------------
    # SHA compare logic
    # ----------------------------------------------------------------------

    def _compare_with_local_shas(self, remote_files):
        """
        Returns list of dicts:
        [
            { "path": "clb.py", "url": "...", "sha": "...", "version": "..." },
            ...
        ]
        """
        updates = []

        for path, info in remote_files.items():
            key = f"sha:{path}"  # how we store local SHAs in settings

            local_sha = self.settings.get(key, None)
            remote_sha = info.get("sha")

            # If no local SHA or mismatch → update required
            if (not local_sha) or (local_sha != remote_sha):
                updates.append({
                    "path": path,
                    "url": info.get("url"),
                    "sha": remote_sha,
                    "version": info.get("version", "0.0.0")
                })

        return updates

    # ----------------------------------------------------------------------
    # Perform updates
    # ----------------------------------------------------------------------

    def _perform_updates(self, updates):
        self.state = self.STATE_UPDATING
        self.set_status(9010, f"Updating {len(updates)} file(s)...")

        for item in updates:
            path = item["path"]
            url = item["url"]
            expected_sha = item["sha"]

            try:
                self._download_and_install(path, url)
                # Save new SHA to settings
                key = f"sha:{path}"
                self.settings[key] = expected_sha
                # persist CLB settings
                try:
                    self.clb.settings["updater"][key] = expected_sha
                except:
                    pass
                self.set_status(9011, f"Updated {path}")
            except Exception as e:
                self.state = self.STATE_ERROR
                self.set_status(9012, f"Update failed ({path}): {e}")
                return

        self.set_status(9013, "All updates installed")
        # Restart if enabled
        if self.settings["auto_restart"]:
            self.pending_restart = True
        else:
            self.state = self.STATE_IDLE
            self._schedule_next()

    def _download_and_install(self, filepath, url):
        self.set_status(9014, f"Downloading {filepath}")

        r = requests.get(url)
        if r.status_code != 200:
            raise OSError(f"HTTP {r.status_code}")

        code = r.text

        # Ensure directory exists
        folder = os.path.dirname(filepath)
        if folder and folder not in ("", "/"):
            try:
                os.mkdir(folder)
            except:
                pass

        tmp = "/update.tmp"

        with open(tmp, "w") as f:
            f.write(code)

        # Atomically replace or create file
        # Remove old file if present
        try:
            os.remove(filepath)
        except:
            pass

        os.rename(tmp, filepath)

    # ----------------------------------------------------------------------
    # Restart system
    # ----------------------------------------------------------------------

    def _restart_system(self):
        self.set_status(9015, "Restarting to apply updates…")
        import machine
        time.sleep(0.2)
        machine.reset()

    # ----------------------------------------------------------------------
    # Console interface
    # ----------------------------------------------------------------------

    def get_interface(self):
        return {
            "check": ("Force update check now", self.cmd_check),
            "restart": ("Restart immediately", self.cmd_restart),
            "status": ("Show updater status", self.cmd_status),
            "list": ("Show known file SHAs", self.cmd_list)
        }

    def cmd_check(self):
        self.next_check_ms = time.ticks_ms() - 1
        self.set_status(9020, "Manual update triggered")

    def cmd_restart(self):
        self.pending_restart = True
        self.set_status(9021, "Manual restart triggered")

    def cmd_status(self):
        print(f"Updater state: {self.state}")
        print(f"Next check in: {time.ticks_diff(self.next_check_ms, time.ticks_ms())} ms")
        print("Enabled:", self.enabled)
        return "OK"

    def cmd_list(self):
        """List stored SHAs for debug."""
        print("Stored SHAs:")
        for k, v in self.settings.items():
            if k.startswith("sha:"):
                print(f"  {k}: {v}")
