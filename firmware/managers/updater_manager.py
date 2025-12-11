# managers/updater_manager.py
#
# Full updater:
#  - manifest fetch
#  - recursive version comparison
#  - safe file download via MQTT (filename.new)
#  - verify + atomic rename
#  - non-blocking state machine
#  - uses get_service_handle() for MQTT
#  - binds events via clb.get_event()
#  - MicroPython compatible
#

import os
import json
from managers.base import CLBManager
from managers.event import Event

MANIFEST_REMOTE = "manifest.json"
MANIFEST_LOCAL  = "_manifest_tmp.json"
RANGE = 2000   # chunk size


class Manager(CLBManager):
    version = "3.1.0"
    dependencies = ["mqtt"]

    (
        PHASE_IDLE,
        PHASE_WAIT_MANIFEST,
        PHASE_COMPARE,
        PHASE_PREP_FILE,
        PHASE_REQUEST_FILE,
        PHASE_WAIT_FILE,
        PHASE_DONE,
        PHASE_ERROR,
    ) = range(8)

    def __init__(self, clb):
        super().__init__(clb, defaults={
            "enabled": True,
            "source": "",
        })

        self._phase = self.PHASE_IDLE
        self._full_update = False
        self.ctx = None
        self.mqtt = None

        self.events = {
            "check.start":        Event("check.start", "Check start", self),
            "check.complete":     Event("check.complete", "Check complete", self),
            "check.error":        Event("check.error", "Check error", self),

            "update.start":       Event("update.start", "Update start", self),
            "update.file_start":  Event("update.file_start", "Update file start", self),
            "update.file_done":   Event("update.file_done", "Update file done", self),
            "update.complete":    Event("update.complete", "Update complete", self),
            "update.error":       Event("update.error", "Update error", self),
        }

    # ---------------------------------------------------------
    # SETUP
    # ---------------------------------------------------------
    def setup(self, settings):
        super().setup(settings)
        self.source = settings["source"] or None
        print("[UPD] setup complete")

    # ---------------------------------------------------------
    # SETUP SERVICES
    # ---------------------------------------------------------
    def setup_services(self):
        print("[UPD] setup_services")

        self.mqtt = self.get_service_handle("mqtt")
        if not self.mqtt:
            print("[UPD] MQTT not available — updater idle")
            return

        print("[UPD] MQTT resolved")

        evt = self.clb.get_event("file.fetch_complete")
        if evt:
            evt.subscribe(self._on_fetch_complete)
            print("[UPD] Bound to file.fetch_complete")

        evt = self.clb.get_event("file.fetch_error")
        if evt:
            evt.subscribe(self._on_fetch_error)
            print("[UPD] Bound to file.fetch_error")

        print("[UPD] Updater service wiring complete")

    # ---------------------------------------------------------
    # COMMAND INTERFACE
    # ---------------------------------------------------------
    def get_interface(self):
        return {
            "check":        ("check - fetch manifest and compare", self.command_check),
            "check_local":  ("check_local - compare with cached manifest", self.command_check_local),
            "update":       ("update - full OTA update", self.command_update),
            "show_versions":("show_versions - print local versions", self.command_show_versions),
        }

    def command_check(self):
        self._start_process(full_update=False, fetch_manifest=True)

    def command_check_local(self):
        self._start_process(full_update=False, fetch_manifest=False)

    def command_update(self):
        self._start_process(full_update=True, fetch_manifest=True)

    def command_show_versions(self):
        for f, v in self._read_local_versions().items():
            print(f"{f}: {v}")

    # ---------------------------------------------------------
    # START PROCESS
    # ---------------------------------------------------------
    def _start_process(self, full_update, fetch_manifest):
        if self._phase not in (self.PHASE_IDLE, self.PHASE_DONE, self.PHASE_ERROR):
            print("[UPD] Cannot start — updater busy")
            return

        if not self.mqtt:
            print("[UPD] Cannot start — MQTT not resolved")
            return

        self._full_update = full_update

        self.ctx = {
            "manifest": None,
            "pending": [],
            "current": None,
        }

        if full_update:
            self.events["update.start"].publish({})
        else:
            self.events["check.start"].publish({})

        self.set_status(5600, "Updater: starting")

        if fetch_manifest:
            print(f"[UPD] Requesting manifest.json (source={self.source})")
            self.mqtt.fetch_file(MANIFEST_REMOTE, MANIFEST_LOCAL, RANGE, self.source)
            self._phase = self.PHASE_WAIT_MANIFEST
        else:
            if not os.path.exists(MANIFEST_LOCAL):
                self._fail("No local manifest available")
                return
            print("[UPD] Using existing manifest")
            self._load_manifest()

    # ---------------------------------------------------------
    # NON-BLOCKING UPDATE LOOP
    # ---------------------------------------------------------
    def update(self):
        if self._phase == self.PHASE_IDLE:
            return

        elif self._phase == self.PHASE_WAIT_MANIFEST:
            return

        elif self._phase == self.PHASE_COMPARE:
            self._compare_manifest()
            return

        elif self._phase == self.PHASE_PREP_FILE:
            self._prep_next_file()
            return

        elif self._phase == self.PHASE_REQUEST_FILE:
            self._request_file()
            return

        elif self._phase == self.PHASE_WAIT_FILE:
            return

        elif self._phase == self.PHASE_DONE:
            if self._full_update:
                self.events["update.complete"].publish({})
            else:
                self.events["check.complete"].publish({})
            self._phase = self.PHASE_IDLE
            print("[UPD] process complete → idle")
            return

        elif self._phase == self.PHASE_ERROR:
            return

    # ---------------------------------------------------------
    # EVENT HANDLERS
    # ---------------------------------------------------------
    def _on_fetch_complete(self, event, data):
        dest = data["dest"]
        file = data["file"]
        size = data.get("bytes", 0)

        print(f"[UPD] fetch_complete: {file} → {dest} ({size} bytes)")

        # Manifest
        if dest == MANIFEST_LOCAL and self._phase == self.PHASE_WAIT_MANIFEST:
            self._load_manifest()
            return

        # File for update
        if self._phase == self.PHASE_WAIT_FILE:
            try:
                self._apply_file_update(self.ctx["current"])
            except Exception as e:
                self._fail(f"File apply failed: {e}")
                return

            self.events["update.file_done"].publish({"file": file})
            self._phase = self.PHASE_PREP_FILE

    def _on_fetch_error(self, event, data):
        print("[UPD] fetch_error:", data)
        self._fail("Fetch error: " + str(data))

    # ---------------------------------------------------------
    # MANIFEST HANDLING
    # ---------------------------------------------------------
    def _load_manifest(self):
        print("[UPD] Reading manifest…")
        try:
            with open(MANIFEST_LOCAL) as fp:
                self.ctx["manifest"] = json.load(fp)
        except Exception as e:
            self._fail(str(e))
            return

        print("[UPD] Manifest loaded")
        self._phase = self.PHASE_COMPARE

    # ---------------------------------------------------------
    # VERSION COMPARISON
    # ---------------------------------------------------------
    def _compare_manifest(self):
        manifest = self.ctx["manifest"]
        local_versions = self._read_local_versions()

        print("[UPD] Comparing versions…")
        pending = []

        for fname, entry in manifest.items():
            remote = entry.get("version", "?")
            local = local_versions.get(fname)

            print(f"[UPD] {fname}: local={local} remote={remote}")

            if local != remote:
                pending.append(fname)

        self.ctx["pending"] = pending

        if not self._full_update:
            print("[UPD] CHECK ONLY — pending updates:")
            for f in pending:
                print("   →", f)
            self._phase = self.PHASE_DONE
            return

        print("[UPD] UPDATE MODE — files that need updating:", pending)
        self._phase = self.PHASE_PREP_FILE

    # ---------------------------------------------------------
    # UPDATE: PREP NEXT FILE
    # ---------------------------------------------------------
    def _prep_next_file(self):
        if not self.ctx["pending"]:
            print("[UPD] All files updated")
            self._phase = self.PHASE_DONE
            return

        fname = self.ctx["pending"].pop(0)
        self.ctx["current"] = fname

        print(f"[UPD] Preparing update for: {fname}")
        self.events["update.file_start"].publish({"file": fname})

        self._phase = self.PHASE_REQUEST_FILE

    # ---------------------------------------------------------
    # REQUEST FILE DOWNLOAD (to .new)
    # ---------------------------------------------------------
    def _request_file(self):
        fname = self.ctx["current"]
        temp = fname + ".new"

        print(f"[UPD] Requesting download: {fname} → {temp}")

        self.mqtt.fetch_file(fname, temp, RANGE, self.source)

        self._phase = self.PHASE_WAIT_FILE

    # ---------------------------------------------------------
    # APPLY DOWNLOADED FILE (safe write + atomic rename)
    # ---------------------------------------------------------
    def _apply_file_update(self, filename):
        newfile = filename + ".new"

        print(f"[UPD] Verifying downloaded file: {newfile}")

        try:
            st = os.stat(newfile)
        except:
            raise RuntimeError("Downloaded file missing")

        size = st[6] if len(st) > 6 else st[0]
        if size <= 0:
            raise RuntimeError("Downloaded file is empty")

        print(f"[UPD] Download OK ({size} bytes)")

        # Remove old file if exists
        try:
            os.remove(filename)
            print(f"[UPD] Removed old: {filename}")
        except:
            pass

        # Atomic rename
        try:
            os.rename(newfile, filename)
            print(f"[UPD] Installed: {filename}")
        except Exception as e:
            raise RuntimeError(f"Rename failed: {e}")

    # ---------------------------------------------------------
    # READ VERSIONS (MicroPython safe)
    # ---------------------------------------------------------
    def _read_local_versions(self):
        versions = {}
        IGNORE = {"__pycache__", ".git", ".vscode"}

        print("[UPD] Scanning local files…")

        def scan(path):
            try:
                items = os.listdir(path)
            except:
                return

            for name in items:
                full = path + "/" + name if path else name

                try:
                    st = os.stat(full)
                except:
                    continue

                mode = st[0]

                # folder?
                if mode & 0x4000:
                    if name not in IGNORE:
                        scan(full)
                    continue

                if full.endswith(".py"):
                    try:
                        with open(full) as fp:
                            for line in fp:
                                if "version" in line and "=" in line:
                                    ver = line.split("=",1)[1].strip().strip('"\'')
                                    versions[full] = ver
                                    print(f"[UPD] Found version: {full} = {ver}")
                                    break
                    except:
                        print("[UPD] Cannot read", full)

        scan(".")
        return versions

    # ---------------------------------------------------------
    # FAIL
    # ---------------------------------------------------------
    def _fail(self, msg):
        print("[UPD] ERROR:", msg)
        self.set_status(5699, msg)

        if self._full_update:
            self.events["update.error"].publish({"error": msg})
        else:
            self.events["check.error"].publish({"error": msg})

        self._phase = self.PHASE_ERROR
