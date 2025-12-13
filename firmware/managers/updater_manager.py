# managers/updater_manager.py
#
# Full updater:
#  - manifest fetch (via MQTT file.fetch)
#  - recursive version comparison over all .py files
#  - safe file download via MQTT (filename.new)
#  - verify + atomic rename
#  - non-blocking state machine using _phase
#  - uses get_service_handle() for MQTT
#  - binds to file.fetch_complete / file.fetch_error via clb.get_event()
#  - MicroPython compatible (no os.walk)
#

import os
import json
from managers.base import CLBManager
from managers.event import Event

MANIFEST_REMOTE = "manifest.json"          # upstream (server or peer)
MANIFEST_LOCAL  = "manifest_local.json"    # generated locally
MANIFEST_TMP    = "_manifest_tmp.json"     # temp download target


class Manager(CLBManager):
    version = "3.1.1"
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
            "source": "",     # optional source device name; empty = server
        })

        self._phase = self.PHASE_IDLE
        self._full_update = False  # True for updater.update, False for check*
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
    # SETUP / SERVICES
    # ---------------------------------------------------------
    def setup(self, settings):
        super().setup(settings)
        self.source = settings["source"] or None
        print("[UPD] setup complete")

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
        else:
            print("[UPD] WARNING: file.fetch_complete event not found")

        evt = self.clb.get_event("file.fetch_error")
        if evt:
            evt.subscribe(self._on_fetch_error)
            print("[UPD] Bound to file.fetch_error")
        else:
            print("[UPD] WARNING: file.fetch_error event not found")

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
    # PROCESS START
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
            "newer":[],
            "current": None,
        }

        self._build_local_manifest()

        if full_update:
            self.events["update.start"].publish({})
        else:
            self.events["check.start"].publish({})

        self.set_status(5600, "Updater: starting")

        if fetch_manifest:
            print(f"[UPD] Requesting {MANIFEST_REMOTE} (source={self.source})")
            self.mqtt.fetch_file(MANIFEST_REMOTE, MANIFEST_TMP, RANGE, self.source)
            self._phase = self.PHASE_WAIT_MANIFEST
        else:
            if not os.path.exists(MANIFEST_REMOTE):
                self._fail("No cached manifest available")
                return
            self._load_manifest(MANIFEST_REMOTE)

    # ---------------------------------------------------------
    # NON-BLOCKING UPDATE LOOP
    # ---------------------------------------------------------
    def update(self):
        if self._phase == self.PHASE_IDLE:
            return

        elif self._phase == self.PHASE_WAIT_MANIFEST:
            return  # waiting for fetch_complete

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
            return  # waiting for fetch_complete

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
        if dest == MANIFEST_TMP and self._phase == self.PHASE_WAIT_MANIFEST:
            self._load_manifest(MANIFEST_TMP)
            return

        # File for update
        if self._phase == self.PHASE_WAIT_FILE:
            try:
                self._apply_file_update(self.ctx["current"])
            except Exception as e:
                self._fail("File apply failed: " + str(e))
                return

            self.events["update.file_done"].publish({"file": file})
            self._phase = self.PHASE_PREP_FILE

    def _on_fetch_error(self, event, data):
        print("[UPD] fetch_error:", data)
        self._fail("Fetch error: " + str(data))

    # ---------------------------------------------------------
    # MANIFEST LOADING
    # ---------------------------------------------------------
    def _load_manifest(self, filename):
        print(f"[UPD] Reading manifest from {filename}")
        try:
            with open(filename) as fp:
                self.ctx["manifest"] = json.load(fp)
        except Exception as e:
            self._fail("Manifest parse error: " + str(e))
            return

        self._phase = self.PHASE_COMPARE

    def _parse_version(self, v):
        return tuple(int(p) for p in v.split("."))

    # ---------------------------------------------------------
    # VERSION COMPARISON (robust manifest iteration)
    # ---------------------------------------------------------
    def _compare_manifest(self):
        manifest = self.ctx["manifest"]
        if manifest is None:
            self._fail("No manifest loaded")
            return

        # Manifest may be:
        #  { "version_id": "...", "generated_at": "...", "files": { "path": {...}, ... } }
        # or directly:
        #  { "path": { "version": "...", "sha": "..." }, ... }
        if isinstance(manifest, dict) and "files" in manifest and isinstance(manifest["files"], dict):
            files_section = manifest["files"]
            print("[UPD] Using manifest['files'] for comparison")
        else:
            files_section = manifest
            print("[UPD] Using top-level manifest entries for comparison")

        local_versions = self._read_local_versions()
        pending = []
        newer = []

        print("[UPD] Comparing versions…")

        for fname, entry in files_section.items():
            if not isinstance(entry, dict):
                # Skip non-file keys like "generated_at", "manifest_version" if they exist here
                print(f"[UPD] Skipping non-dict manifest entry: {fname}")
                continue

            remote = entry.get("version", None)
            
            if remote is None:
                print(f"[UPD] No 'version' field for {fname} in manifest; skipping")
                continue

            local = local_versions.get(fname)

            print(f"[UPD] {fname}: device={fname} local={local} remote={remote}")

            # Missing locally → needs download
            if local is None:
                pending.append(fname)
                continue

            try:
                lv = self._parse_version(local)
                rv = self._parse_version(remote)
            except Exception:
                # If versions are malformed, be conservative
                pending.append(fname)
                continue

            if lv < rv:
                # Local older → update
                pending.append(fname)

            elif lv > rv:
                # Local newer → warn only
                newer.append({
                    "file": fname,
                    "local": local,
                    "remote": remote
                })

            # else: equal → do nothing

        self.ctx["pending"] = pending
        self.ctx["newer"] = newer

        if not self._full_update:
            print("[UPD] CHECK ONLY — pending updates:")
            for f in pending:
                print("   →", f)
            if newer:
                print("[UPD] WARNING: local files newer than manifest:")
                for n in newer:
                    print(f"   {n['file']}: local={n['local']} remote={n['remote']}")
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
            raise RuntimeError("Rename failed: " + str(e))


    # ---------------------------------------------------------
    # READ VERSIONS (MicroPython safe, full tree)
    # ---------------------------------------------------------
    def _read_local_versions(self):
        versions = {}
        IGNORE = {"__pycache__", ".git", ".vscode"}

        print("[UPD] Scanning local files for version=…")

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

                # Directory
                if mode & 0x4000:
                    if name not in IGNORE:
                        scan(full)
                    continue

                # Python source file
                if not full.endswith(".py"):
                    continue

                try:
                    with open(full) as fp:
                        for line in fp:
                            if "version" in line and "=" in line:
                                ver = line.split("=", 1)[1].strip().strip('"\'')
                                norm = self._normalize_fs_path(full)

                                # ONE canonical entry per file
                                versions[norm] = ver

                                print(f"[UPD] Found version: {norm} = {ver}")
                                break
                except Exception as e:
                    print("[UPD] Cannot read", full, ":", e)

        scan(".")
        return versions


    def _build_local_manifest(self):
        versions = self._read_local_versions()
        manifest = {"files": {}}

        for path, ver in versions.items():
            manifest["files"][path] = {"version": ver}

        try:
            with open(MANIFEST_LOCAL, "w") as fp:
                json.dump(manifest, fp)
            print("[UPD] Built manifest_local.json")
        except Exception as e:
            self._fail("Failed to write manifest_local.json: " + str(e))

    # ---------------------------------------------------------
    # PATH NORMALISATION
    # ---------------------------------------------------------
    def _normalize_fs_path(self, path: str) -> str:
        # For paths coming from the Pico filesystem
        path = path.replace("\\", "/")

        # remove leading ./ and /
        if path.startswith("./"):
            path = path[2:]
        if path.startswith("/"):
            path = path[1:]

        return path


    def _normalize_manifest_path(self, path: str) -> str:
        # For paths coming from the manifest (repo layout)
        path = path.replace("\\", "/")

        # manifest paths are typically relative, but be defensive
        if path.startswith("./"):
            path = path[2:]
        if path.startswith("/"):
            path = path[1:]

        # map repo layout -> device layout
        if path.startswith("firmware/"):
            path = path[len("firmware/"):]
        return path

    # ---------------------------------------------------------
    # FAIL STATE
    # ---------------------------------------------------------
    def _fail(self, msg):
        print("[UPD] ERROR:", msg)
        self.set_status(5699, msg)

        if self._full_update:
            self.events["update.error"].publish({"error": msg})
        else:
            self.events["check.error"].publish({"error": msg})

        self._phase = self.PHASE_ERROR
