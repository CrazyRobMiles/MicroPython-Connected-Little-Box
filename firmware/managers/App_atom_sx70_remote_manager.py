# managers/sx70r_manager.py
#
# SX-70R BLE Camera Manager for Connected Little Boxes (CLB)
#
# This is a CLB "first-class" manager:
# - Lifecycle: setup, setup_services, update, teardown
# - Unified settings persistence via clb.config.save()
# - Provides services via get_interface()
# - Publishes CLB events other managers can bind to
#
# Key design choices:
# - Scan by advertised name "CH9141BLE2U" (as per your real-world observation).
# - Optional address approval workflow to handle multiple devices with same name.
# - Non-blocking operation using CLB yielding state machine (no uasyncio).
#
# Services:
#   sx70r.connect
#   sx70r.disconnect
#   sx70r.scan_register
#   sx70r.approved
#   sx70r.set_preferred <AA:BB:CC:DD:EE:FF>
#   sx70r.request_iso
#   sx70r.get_iso
#   sx70r.fire_shutter <exp_hex> [self_timer_s] [t_hold_ms]
#
# Events:
#   camera.connected
#   camera.disconnected
#   camera.iso
#   camera.exposure_started
#   camera.exposure_finished
#   camera.error
#
from managers.base_manager import CLBManager
from managers.event import Event

import bluetooth
import time
import machine
import neopixel
from collections import deque


# ------------------------------
# Protocol constants
# ------------------------------
NAME_MATCH = "CH9141BLE2U"

UUID_FFF0 = bluetooth.UUID(0xFFF0)
UUID_FFF1 = bluetooth.UUID(0xFFF1)  # notify/read
UUID_FFF2 = bluetooth.UUID(0xFFF2)  # write
UUID_CCCD = bluetooth.UUID(0x2902)

CMD_ISO_QUERY = b"\xDD\xDD\xDD\xDD"
CMD_FIRE      = b"\xEE\xEE\xEE\xEE"

AE_SHUTTER = b"\x00\x01"  # 00 01 = Auto exposure
T_SHUTTER  = b"\x00\x02"  # 00 02 = T mode

# Prefer symbolic IRQ constants where available; fall back to typical rp2 numeric values.
_IRQ_SCAN_RESULT               = getattr(bluetooth, "IRQ_SCAN_RESULT", 5)
_IRQ_SCAN_DONE                 = getattr(bluetooth, "IRQ_SCAN_DONE", 6)
_IRQ_PERIPHERAL_CONNECT        = getattr(bluetooth, "IRQ_PERIPHERAL_CONNECT", 7)
_IRQ_PERIPHERAL_DISCONNECT     = getattr(bluetooth, "IRQ_PERIPHERAL_DISCONNECT", 8)
_IRQ_GATTC_SERVICE_RESULT      = getattr(bluetooth, "IRQ_GATTC_SERVICE_RESULT", 9)
_IRQ_GATTC_SERVICE_DONE        = getattr(bluetooth, "IRQ_GATTC_SERVICE_DONE", 10)
_IRQ_GATTC_CHARACTERISTIC_RESULT = getattr(bluetooth, "IRQ_GATTC_CHARACTERISTIC_RESULT", 11)
_IRQ_GATTC_CHARACTERISTIC_DONE = getattr(bluetooth, "IRQ_GATTC_CHARACTERISTIC_DONE", 12)
_IRQ_GATTC_DESCRIPTOR_RESULT   = getattr(bluetooth, "IRQ_GATTC_DESCRIPTOR_RESULT", 13)
_IRQ_GATTC_DESCRIPTOR_DONE     = getattr(bluetooth, "IRQ_GATTC_DESCRIPTOR_DONE", 14)
_IRQ_GATTC_READ_RESULT         = getattr(bluetooth, "IRQ_GATTC_READ_RESULT", 15)
_IRQ_GATTC_READ_DONE           = getattr(bluetooth, "IRQ_GATTC_READ_DONE", 16)
_IRQ_GATTC_WRITE_DONE          = getattr(bluetooth, "IRQ_GATTC_WRITE_DONE", 17)
_IRQ_GATTC_NOTIFY              = getattr(bluetooth, "IRQ_GATTC_NOTIFY", 18)
_IRQ_GATTC_INDICATE            = getattr(bluetooth, "IRQ_GATTC_INDICATE", 19)

# ------------------------------
# Small helpers
# ------------------------------
def _mac_bytes_to_str(b):
    return ":".join("{:02X}".format(x) for x in b)

def _adv_decode_name(adv_data):
    # Parse AD structures for Complete Local Name / Shortened Local Name
    # Types: 0x09 (Complete), 0x08 (Shortened)
    if not adv_data:
        return None
    adv_data = bytes(adv_data)
    i = 0
    n = len(adv_data)
    while i + 1 < n:
        ln = adv_data[i]
        if ln == 0:
            break
        if i + 1 + ln > n:
            break
        t = adv_data[i + 1]
        if t in (0x08, 0x09):
            raw = adv_data[i + 2 : i + 1 + ln]
            try:
                return bytes(raw).decode("utf-8")
            except Exception:
                return None
        i += 1 + ln
    return None


class Manager(CLBManager):
    version = "0.2.0"

    STATE_IDLE        = "idle"
    STATE_SCANNING    = "scanning"
    STATE_CONNECTING  = "connecting"
    STATE_CONNECTED   = "connected"
    STATE_ERROR       = "error"
    STATE_DISABLED    = "disabled"

    def __init__(self, clb):
        super().__init__(clb, defaults={
            "enabled": True,

            # Behaviour
            "auto_connect": True,
            "scan_ms": 6000,
            "reconnect_backoff_ms": 2000,

            # Registration / selection
            "approved_addrs": [],      # list of "AA:BB:CC:DD:EE:FF"
            "preferred_addr": "",      # optional "AA:BB:..."
            "require_approval": True,  # if True, connect only to approved/preferred devices

            # Debug
            "debug": True,
        })

        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._irq)

        # Queue of high-level commands (non-blocking)
        self._q = deque((), 30)
        self._pending = None

        self._reset_ble_state()

        # Cached values
        self._last_iso = None

        # Timing
        self._last_connect_attempt_ms = 0

        # Registration mode blocks auto-connect and ensures flag cleanup.
        self._registration_mode = False
        
        self._awaiting_fire_status = False
        self._last_fire_status = None
        

        # Events (published to CLB event system)
        self.events = {
            "camera.connected":         Event("camera.connected", "Camera BLE connected", self),
            "camera.disconnected":      Event("camera.disconnected", "Camera BLE disconnected", self),
            "camera.iso":               Event("camera.iso", "ISO value received", self),
            "camera.exposure_started":  Event("camera.exposure_started", "Exposure started", self),
            "camera.exposure_finished": Event("camera.exposure_finished", "Exposure finished", self),
            "camera.error":             Event("camera.error", "Camera error", self),
        }

    # ------------------------------
    # CLB lifecycle
    # ------------------------------
    def setup(self, settings):
        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            self.set_status(3000, "SX-70R camera disabled by config")
            return

        self.debug = bool(self.settings.get("debug", False))
        self.state = self.STATE_IDLE
        self.set_status(3001, "SX-70R camera manager ready")

    def setup_services(self):
        # No external dependencies required.
        self.button_pin =  machine.Pin(39, machine.Pin.IN,machine.Pin.PULL_UP)
        self.pixels = neopixel.NeoPixel(machine.Pin(27, machine.Pin.OUT), 25)
        self.pixels.fill((10,10,10))
        self.pixels.write()
        self.connected=False
        self.old_connected=True
        self.pressed_count=0

    def update(self):
        
        if not self.enabled:
            return

        if self.connected != self.old_connected:
            if self.connected:
                self.pixels.fill((10,50,10))
            else:
                self.pixels.fill((50,10,10))
            self.pixels.write()
            self.old_connected = self.connected
            
        if not self.button_pin.value():
            self.pressed_count=self.pressed_count+1
            if self.pressed_count==100:
                if self.connected:
                    self.command_fire_shutter("FFFF0001")
        else:                
            self.pressed_count=0

        # Drive any active yielding state
        self.update_yielding()
        if getattr(self, "_current", None):
            return

        # Registration mode: do not auto-connect, do not process queue
        if self._registration_mode:
            return

        # Auto-connect if enabled
        if not self._is_connected():
            if self.settings.get("auto_connect", True):
                now = time.ticks_ms()
                if time.ticks_diff(now, self._last_connect_attempt_ms) > int(self.settings.get("reconnect_backoff_ms", 2000)):
                    self._last_connect_attempt_ms = now
                    self.change_state(self._state_connect_flow, "connect_flow")
            return

        # Process queued commands when connected
        if self._q:
            cmd = self._q.popleft()
            self.change_state(self._state_run_command, "run_command", cmd)

    def teardown(self):
        self._disconnect(reason="teardown")
        try:
            self.ble.active(False)
        except Exception:
            pass
        self.set_status(3010, "SX-70R camera BLE disabled")

    # ------------------------------
    # Published events helper
    # ------------------------------
    def get_published_events(self):
        return [{"name": e.name, "description": e.description} for e in self.events.values()]

    # ------------------------------
    # Interface (services)
    # ------------------------------
    def get_interface(self):
        return {
            # Connection control
            "connect":        ("Connect to camera now (scan by name first)", self.command_connect),
            "disconnect":     ("Disconnect camera", self.command_disconnect),

            # Registration
            "scan_register":  ("Scan and approve a camera address", self.command_scan_register),
            "approved":       ("Show approved addresses", self.command_show_approved),
            "set_preferred":  ("set_preferred <AA:BB:CC:DD:EE:FF> (empty clears; auto-approves)", self.command_set_preferred),

            # ISO
            "request_iso":    ("Request ISO (non-blocking; emits camera.iso)", self.command_request_iso),
            "get_iso":        ("Return cached ISO or None", self.command_get_iso),

            # Shutter
            "fire_shutter":   ("fire_shutter <exp_hex> [self_timer_s] [t_hold_ms]", self.command_fire_shutter),
        }

    # ---- CLI wrappers ----
    def command_connect(self):
        if not getattr(self, "_current", None):
            self.change_state(self._state_connect_flow, "connect_flow")
        return True

    def command_disconnect(self):
        self._disconnect(reason="manual")
        return True

    def command_show_approved(self):
        return self.settings.get("approved_addrs", [])

    def command_set_preferred(self, addr=""):
        addr = (addr or "").strip().upper()
        self.settings["preferred_addr"] = addr

        # Auto-approve preferred address (matches your expectation and prevents "found but not approved")
        if addr:
            approved = [a.upper() for a in (self.settings.get("approved_addrs", []) or [])]
            if addr not in approved:
                approved.append(addr)
            self.settings["approved_addrs"] = approved

        self._save_settings()
        return addr

    def command_scan_register(self):
        # Pre-empt any yielding state and enter registration mode.
        # This makes scan_register reliable even with auto_connect enabled.
        self._enter_registration_mode()
        self.change_state(self._state_scan_and_register, "scan_register")
        return True

    def command_request_iso(self):
        self._enqueue({"type": "iso"})
        return True

    def command_get_iso(self):
        return self._last_iso

    def command_fire_shutter(self, exp_hex, self_timer_s=0, t_hold_ms=2000):
        # exp_hex is 8 hex chars (4 bytes), e.g. "FFFF0001" for AE or "FFFF0002" for T
        exp_hex = (exp_hex or "").strip().replace("0x", "").replace("0X", "")
        if len(exp_hex) != 8:
            raise ValueError("exp_hex must be 8 hex chars, e.g. FFFF0001")
        exposure = bytes.fromhex(exp_hex)

        delay_ms = int(float(self_timer_s) * 1000)
        t_hold_ms = int(t_hold_ms)

        self._enqueue({
            "type": "fire",
            "exposure": exposure,
            "delay_ms": delay_ms,
            "t_hold_ms": t_hold_ms,
        })
        return True

    # ------------------------------
    # Registration mode helpers
    # ------------------------------
    def _enter_registration_mode(self):
        # Cancel yielding flow, clear queue, disconnect, block auto-connect until scan/register completes.
        self._registration_mode = True
        try:
            self._current = None
        except Exception:
            pass
        try:
            self._q.clear()
        except Exception:
            pass
        self._disconnect(reason="registration")

    def _exit_registration_mode(self):
        self._registration_mode = False

    # ------------------------------
    # Internal queueing
    # ------------------------------
    def _enqueue(self, item):
        if len(self._q) >= 30:
            self.events["camera.error"].publish({"error": "queue_full"})
            return False
        self._q.append(item)
        return True

    # ------------------------------
    # BLE state
    # ------------------------------
    def _reset_ble_state(self):
        self._conn_handle = None

        # Discovered handles
        self._svc_start = None
        self._svc_end = None
        self._fff1_val = None
        self._fff2_val = None
        self._cccd_handle = None

        # Discovery done flags
        self._svc_done = False
        self._chr_done = False
        self._dsc_done = False

        # Scan state
        self._scan_results = []   # list of dicts
        self._scan_done = False
        
        self._read_done = False
        self._last_read = None

        self._write_done = False
        

    def _is_connected(self):
        return self._conn_handle is not None

    # ------------------------------
    # BLE IRQ handler
    # ------------------------------
    def _irq(self, event, data):
        # IDs are stable on rp2 builds:
        # 5 scan result, 6 scan done, 7 connect, 8 disconnect,
        # 9 svc result, 10 svc done, 11 char result, 12 char done,
        # 13 desc result, 14 desc done, 18 notify, 19 indicate.
        
        if self.debug and event in (_IRQ_GATTC_SERVICE_DONE, _IRQ_GATTC_CHARACTERISTIC_DONE, _IRQ_GATTC_DESCRIPTOR_DONE):
            print("[camera] DONE event", event, "data", data)
        
        try:
            if event == _IRQ_SCAN_RESULT:
                addr_type, addr, adv_type, rssi, adv_data = data
                name = _adv_decode_name(adv_data)

                if name != NAME_MATCH:
                    return

                addr_b = bytes(addr)
                addr_str = _mac_bytes_to_str(addr_b)

                # De-dup by address; keep best RSSI
                for r in self._scan_results:
                    if r["addr_str"] == addr_str:
                        if rssi > r["rssi"]:
                            r["rssi"] = rssi
                        return

                rec = {
                    "name": name,
                    "addr_type": addr_type,
                    "addr": addr_b,
                    "addr_str": addr_str,
                    "rssi": rssi,
                }
                self._scan_results.append(rec)
                if self.debug:
                    print("[camera] scan match:", name, addr_str, "rssi", rssi)

            elif event == _IRQ_SCAN_DONE:
                self._scan_done = True

            elif event == _IRQ_PERIPHERAL_CONNECT:
                conn_handle, addr_type, addr = data
                self._conn_handle = conn_handle
                if self.debug:
                    print("[camera] CONNECTED:", conn_handle, _mac_bytes_to_str(bytes(addr)))
                self.events["camera.connected"].publish({"handle": conn_handle})
                self.connected=True


            elif event == _IRQ_PERIPHERAL_DISCONNECT:
                conn_handle, addr_type, addr = data
                if self.debug:
                    print("[camera] DISCONNECTED:", conn_handle)
                self._disconnect(reason="peer")
                self.connected=False
                self.events["camera.disconnected"].publish({})

            elif event == _IRQ_GATTC_SERVICE_RESULT:
                conn_handle, start_handle, end_handle, uuid = data
                if uuid == UUID_FFF0:
                    self._svc_start, self._svc_end = start_handle, end_handle

            elif event == _IRQ_GATTC_SERVICE_DONE:
                self._svc_done = True

            elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
                conn_handle, def_handle, value_handle, properties, uuid = data
                self._saw_chr_result = True
                if uuid == UUID_FFF1:
                    self._fff1_val = value_handle
                elif uuid == UUID_FFF2:
                    self._fff2_val = value_handle

            elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
                self._chr_done = True

            elif event == _IRQ_GATTC_DESCRIPTOR_RESULT:
                conn_handle, dhandle, uuid = data
                if uuid == UUID_CCCD:
                    # Prefer the CCCD that is closest *above* FFF1 value handle.
                    if dhandle > (self._fff1_val or 0):
                        if (self._cccd_handle is None) or (dhandle < self._cccd_handle):
                            self._cccd_handle = dhandle

            elif event == _IRQ_GATTC_DESCRIPTOR_DONE:
                self._dsc_done = True

            elif event == _IRQ_GATTC_READ_RESULT:
                conn_handle, value_handle, read_data = data
                if value_handle == self._fff1_val:
                    payload = bytes(read_data)
                    self._last_read = payload
                    # Reuse same parser/notification handler
                    self._handle_fff1_notification(payload)

            elif event == _IRQ_GATTC_READ_DONE:
                # data is typically (conn_handle, status)
                self._read_done = True
            
            elif event == _IRQ_GATTC_WRITE_DONE:
                # Usually: (conn_handle, value_handle, status)
                # We don't depend on exact shape; mark write done.
                self._write_done = True
                if self.debug:
                    try:
                        print("[camera] WRITE_DONE", data)
                    except Exception:
                        pass

            elif event in (_IRQ_GATTC_NOTIFY, _IRQ_GATTC_INDICATE):
                conn_handle, value_handle, notify_data = data
                if value_handle == self._fff1_val:
                    self._handle_fff1_notification(bytes(notify_data))

        except Exception as e:
            # Keep IRQ handler resilient
            self.events["camera.error"].publish({"error": "irq_exception", "detail": str(e)})

    def _handle_fff1_notification(self, payload):
        if self.debug:
            print("[camera] FFF1 notify:", payload)

        # Fire status / ACK from camera (observed as 2 bytes, e.g. 00 1E)
        if len(payload) == 2 and self._awaiting_fire_status:
            self._last_fire_status = payload
            self._awaiting_fire_status = False

            self.events["camera.exposure_finished"].publish({
                "raw": payload,
                "code": payload[0],
                "detail": payload[1],
            })

            if self.debug:
                print("[sx70r] FIRE status:", payload)
            return
        
        iso = self._try_parse_iso(payload)
        if iso is not None:
            self._last_iso = iso
            self.events["camera.iso"].publish({"iso": iso})
            if self._pending and self._pending.get("type") == "iso":
                self._pending["done"] = True

    def _try_parse_iso(self, payload):
        # ISO response is often 1 byte on this device:
        # 0xAA = ISO 600, 0xBB = ISO SX-70
        if not payload:
            return None

        # 1-byte ISO code (preferred)
        if len(payload) == 1:
            b = payload[0]
            if b == 0xAA:
                return 600
            if b == 0xBB:
                # You can return a sentinel or a numeric; choose what your app expects.
                # Returning 160 is not correct; SX-70 is a film type, not a number.
                # Use a string or a special value.
                return "SX-70"
            return None

        # Fallback: heuristic for 16-bit values in other firmware variants
        if len(payload) >= 2:
            for i in range(len(payload) - 1):
                v = payload[i] | (payload[i + 1] << 8)
                if 50 <= v <= 6400:
                    return v

        return None

    # ------------------------------
    # Yielding state machines
    # ------------------------------
    def _state_scan(self, scan_ms):
        self.state = self.STATE_SCANNING
        self._scan_results = []
        self._scan_done = False

        if self.debug:
            print("[camera] SCANNING for", NAME_MATCH)

        # Active scan is essential on many devices to receive SCAN_RSP payloads with the name.
        try:
            self.ble.gap_scan(scan_ms, 30000, 30000, True)
        except TypeError:
            self.ble.gap_scan(scan_ms, 30000, 30000)

        start = time.ticks_ms()
        while (not self._scan_done) and (time.ticks_diff(time.ticks_ms(), start) < (scan_ms + 1000)):
            yield

        try:
            self.ble.gap_scan(None)
        except Exception:
            pass

        if self.debug:
            print("[camera] SCAN DONE matches:", len(self._scan_results))

        self.state = self.STATE_IDLE
        yield

    def _state_connect_flow(self):
        # Determine allowed addresses
        require_approval = bool(self.settings.get("require_approval", True))
        approved = [a.upper() for a in (self.settings.get("approved_addrs", []) or [])]
        preferred = (self.settings.get("preferred_addr", "") or "").upper().strip()

        # Scan by name
        scan_ms = int(self.settings.get("scan_ms", 6000))
        yield from self._state_scan(scan_ms)

        if not self._scan_results:
            self.state = self.STATE_IDLE
            self.set_status(3020, "No camera found in scan")
            return

        # Select target
        selected = None
        if preferred:
            for c in self._scan_results:
                if c["addr_str"] == preferred:
                    selected = c
                    break

        if selected is None and require_approval and approved:
            candidates = [c for c in self._scan_results if c["addr_str"] in approved]
            if candidates:
                selected = sorted(candidates, key=lambda x: x["rssi"], reverse=True)[0]

        if selected is None and not require_approval:
            selected = sorted(self._scan_results, key=lambda x: x["rssi"], reverse=True)[0]

        if selected is None:
            self.state = self.STATE_IDLE
            self.set_status(3021, "Camera found but not approved")
            self.events["camera.error"].publish({
                "error": "not_approved",
                "hint": "Run sx70r.scan_register or add address to approved_addrs / set_preferred"
            })
            return

        # Connect
        self.state = self.STATE_CONNECTING
        self.set_status(3022, "Connecting to camera")
        if self.debug:
            print("[camera] CONNECTING to", selected["addr_str"], "rssi", selected["rssi"])

        try:
            self.ble.gap_connect(selected["addr_type"], selected["addr"])
        except Exception as e:
            self.state = self.STATE_ERROR
            self.set_status(3023, "gap_connect failed: " + str(e))
            self.events["camera.error"].publish({"error": "gap_connect", "detail": str(e)})
            return

        # Wait for connect IRQ
        start = time.ticks_ms()
        while (not self._is_connected()) and (time.ticks_diff(time.ticks_ms(), start) < 8000):
            yield

        if not self._is_connected():
            self.state = self.STATE_IDLE
            self.set_status(3024, "Connect timeout")
            return

        # Discover
        ok = yield from self._state_discover()
        if not ok:
            if self.debug:
                print("[camera] discover failed; retrying once")
            # retry once without disconnecting
            ok = yield from self._state_discover()

        if not ok:
            self._disconnect(reason="discover_failed")
            self.state = self.STATE_IDLE
            return

        # Enable notifications
        ok = yield from self._state_enable_notify()
        if not ok:
            self._disconnect(reason="notify_failed")
            self.state = self.STATE_IDLE
            return

        self.state = self.STATE_CONNECTED
        self.set_status(3030, "Camera connected")
        yield
        
    def _gatt_write_wait(self, value_handle, payload, mode, timeout_ms=1200):
        """
        mode: 0 = write with response, 1 = write without response (MicroPython convention)
        """
        self._write_done = False

        try:
            self.ble.gattc_write(self._conn_handle, value_handle, payload, mode)
        except Exception as e:
            if self.debug:
                print("[sx70r] gattc_write ERROR:", e)
            self.events["camera.error"].publish({"error": "gattc_write", "detail": str(e)})
            return False

        # Always give BLE IRQ a chance to run
        yield

        # If mode == 1 (no response), some stacks never emit WRITE_DONE. Still wait briefly.
        start = time.ticks_ms()
        while (not self._write_done) and (time.ticks_diff(time.ticks_ms(), start) < timeout_ms):
            yield

        return True

    def _state_discover(self):
        
        self._read_done = False
        self._last_read = None
        
        # Reset discovered handles + done flags for this connection
        self._svc_start = self._svc_end = None
        self._fff1_val = self._fff2_val = None
        self._cccd_handle = None

        self._svc_done = False
        self._chr_done = False
        self._dsc_done = False

        if self.debug:
            print("[camera] DISCOVER SERVICES")
        try:
            self.ble.gattc_discover_services(self._conn_handle)
        except Exception as e:
            self.events["camera.error"].publish({"error": "discover_services", "detail": str(e)})
            return False

        start = time.ticks_ms()
        while (not self._svc_done) and (time.ticks_diff(time.ticks_ms(), start) < 6000):
            yield

        if self._svc_start is None:
            if self.debug:
                print("[camera] FFF0 not found")
            return False

        if self.debug:
            print("[camera] FFF0 svc:", self._svc_start, "-", self._svc_end)
            print("[camera] DISCOVER CHARS")

        # IMPORTANT: reset the flag immediately before starting char discovery
        self._chr_done = False
        # Track whether we saw any characteristic result callbacks in this phase
        self._saw_chr_result = False

        try:
            self.ble.gattc_discover_characteristics(self._conn_handle, self._svc_start, self._svc_end)
        except Exception as e:
            self.events["camera.error"].publish({"error": "discover_chars", "detail": str(e)})
            return False

        # Give the BLE stack at least one scheduler tick to deliver CHAR_RESULT IRQs
        yield

        start = time.ticks_ms()
        while (not self._chr_done) and (time.ticks_diff(time.ticks_ms(), start) < 6000):
            yield

        # If we never saw a characteristic result, treat this as a discovery failure
        # (prevents false-positive "done" with no results)
        if not getattr(self, "_saw_chr_result", False):
            if self.debug:
                print("[camera] No characteristic results received")
            return False

        if self._fff1_val is None or self._fff2_val is None:
            if self.debug:
                print("[camera] Missing FFF1/FFF2 handles")
            return False

        if self.debug:
            print("[camera] FFF1 val:", self._fff1_val, "FFF2 val:", self._fff2_val)
            print("[camera] DISCOVER DESCS")

        try:
            self.ble.gattc_discover_descriptors(self._conn_handle, self._svc_start, self._svc_end)
        except Exception as e:
            self.events["camera.error"].publish({"error": "discover_descs", "detail": str(e)})
            return False

        start = time.ticks_ms()
        while (not self._dsc_done) and (time.ticks_diff(time.ticks_ms(), start) < 6000):
            yield

        if self._cccd_handle is None:
            if self.debug:
                print("[camera] CCCD not found")
            return False

        if self.debug:
            print("[camera] CCCD:", self._cccd_handle)
        return True

    def _state_enable_notify(self):
        if self._cccd_handle is None:
            return False
        if self.debug:
            print("[camera] ENABLING NOTIFY")
        try:
            # 0x0001 enables notifications
            self.ble.gattc_write(self._conn_handle, self._cccd_handle, b"\x01\x00", 1)
        except Exception as e:
            self.events["camera.error"].publish({"error": "enable_notify", "detail": str(e)})
            return False

        # Give BLE stack a moment
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < 300:
            yield
        return True

    def _state_scan_and_register(self):
        # Always clear registration_mode on exit, even if user cancels or errors.
        try:
            scan_ms = int(self.settings.get("scan_ms", 6000))
            yield from self._state_scan(scan_ms)

            if not self._scan_results:
                print("[sx70r] No candidates found.")
                return

            # Already de-duped by address in IRQ handler; sort by RSSI.
            candidates = sorted(self._scan_results, key=lambda x: x["rssi"], reverse=True)

            print("\n[sx70r] Candidates ({}):".format(NAME_MATCH))
            for i, c in enumerate(candidates):
                print("  {}: {}  rssi={}".format(i, c["addr_str"], c["rssi"]))

            print("\nEnter index to approve (blank cancels):")
            try:
                s = input("> ").strip()
            except Exception:
                s = ""

            if not s:
                print("[sx70r] Cancelled.")
                return

            try:
                idx = int(s)
                chosen = candidates[idx]
            except Exception:
                print("[sx70r] Invalid selection.")
                return

            approved = [a.upper() for a in (self.settings.get("approved_addrs", []) or [])]
            if chosen["addr_str"] not in approved:
                approved.append(chosen["addr_str"])
            self.settings["approved_addrs"] = approved

            # If no preferred, set preferred to chosen.
            if not (self.settings.get("preferred_addr") or "").strip():
                self.settings["preferred_addr"] = chosen["addr_str"]

            self._save_settings()
            print("[sx70r] Approved:", chosen["addr_str"])
            yield

        finally:
            self._exit_registration_mode()

    def _state_run_command(self, cmd):
        if not self._is_connected():
            return

        ctype = cmd.get("type")
        self._pending = {"type": ctype, "done": False}

        if ctype == "iso":
            if self.debug:
                print("[sx70r] ISO QUERY")

            # Clear any previous read state
            self._read_done = False
            self._last_read = None

            # Write ISO query
            try:
                self.ble.gattc_write(self._conn_handle, self._fff2_val, CMD_ISO_QUERY, 1)
            except Exception as e:
                self.events["camera.error"].publish({"error": "iso_write", "detail": str(e)})
                return

            # IMPORTANT: always yield at least once so CLB doesn't complete this state immediately
            yield

            # Wait briefly for notify-driven ISO response
            start = time.ticks_ms()
            while (not self._pending.get("done")) and (time.ticks_diff(time.ticks_ms(), start) < 800):
                yield

            # Fallback: if no ISO yet, attempt a read of FFF1
            if not self._pending.get("done"):
                if self.debug:
                    print("[sx70r] ISO notify not seen; reading FFF1 as fallback")
                self._read_done = False
                try:
                    self.ble.gattc_read(self._conn_handle, self._fff1_val)
                except Exception as e:
                    self.events["camera.error"].publish({"error": "iso_read_start", "detail": str(e)})
                    self._pending = None
                    return

                # Wait for read result/done
                start = time.ticks_ms()
                while (not self._pending.get("done")) and (not self._read_done) and (time.ticks_diff(time.ticks_ms(), start) < 1500):
                    yield

            # Done (either parsed ISO or timed out)
            if self.debug:
                print("[sx70r] ISO cached:", self._last_iso)

            self._pending = None
            return
        if ctype == "fire":
            exposure = cmd.get("exposure", b"\xFF\xFF\x00\x01")
            delay_ms = int(cmd.get("delay_ms", 0))
            t_hold_ms = int(cmd.get("t_hold_ms", 2000))

            if self.debug:
                print("[sx70r] FIRE REQUEST exposure=", exposure, "delay_ms=", delay_ms, "t_hold_ms=", t_hold_ms)

            # Self-timer delay
            if delay_ms > 0:
                if self.debug:
                    print("[sx70r] SELF TIMER:", delay_ms, "ms")
                start = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), start) < delay_ms:
                    yield

            self.events["camera.exposure_started"].publish({"exposure": exposure.hex()})

            # 1) Set exposure (write-without-response is OK here)
            if self.debug:
                print("[sx70r] SET EXPOSURE:", exposure)

            ok = yield from self._gatt_write_wait(self._fff2_val, exposure, mode=1, timeout_ms=300)
            if not ok:
                if self.debug:
                    print("[sx70r] SET EXPOSURE failed; aborting")
                return

            # Let the camera apply the exposure settings
            start = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), start) < 80:
                yield

            # 2) Fire behaviour
            shutter_code = exposure[2:4]
            if self.debug:
                print("[sx70r] shutter_code:", shutter_code)

            if shutter_code == AE_SHUTTER:
                if self.debug:
                    print("[sx70r] FIRE (AE)")
                # Fire is critical: use write-with-response for reliability
                ok = yield from self._gatt_write_wait(self._fff2_val, CMD_FIRE, mode=0, timeout_ms=1200)
                if not ok:
                    if self.debug:
                        print("[sx70r] FIRE (AE) failed")
                    return

                # Wait for camera status notify indicating completion
                self._awaiting_fire_status = True
                start = time.ticks_ms()
                while self._awaiting_fire_status and time.ticks_diff(time.ticks_ms(), start) < 2000:
                    yield

                # Fallback if no status notify arrived
                if self._awaiting_fire_status:
                    self._awaiting_fire_status = False
                    self.events["camera.exposure_finished"].publish({"mode": "AE", "fallback": True})
                self._pending = None
                return

            if shutter_code == T_SHUTTER:
                if self.debug:
                    print("[sx70r] T MODE: OPEN")
                ok = yield from self._gatt_write_wait(self._fff2_val, CMD_FIRE, mode=0, timeout_ms=1200)
                if not ok:
                    if self.debug:
                        print("[sx70r] T OPEN failed")
                    return

                start = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), start) < t_hold_ms:
                    yield

                if self.debug:
                    print("[sx70r] T MODE: CLOSE")
                ok = yield from self._gatt_write_wait(self._fff2_val, CMD_FIRE, mode=0, timeout_ms=1200)
                if not ok:
                    if self.debug:
                        print("[sx70r] T CLOSE failed")
                    return

                self.events["camera.exposure_finished"].publish({"mode": "T", "hold_ms": t_hold_ms})
                self._pending = None
                return

            # Fixed shutter: single fire
            if self.debug:
                print("[sx70r] FIRE (fixed)")
            ok = yield from self._gatt_write_wait(self._fff2_val, CMD_FIRE, mode=0, timeout_ms=1200)
            if not ok:
                if self.debug:
                    print("[sx70r] FIRE (fixed) failed")
                return

            start = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), start) < 1000:
                yield

            self.events["camera.exposure_finished"].publish({"mode": "fixed"})
            self._pending = None
            return

    # ------------------------------
    # Disconnect / persistence
    # ------------------------------
    def _disconnect(self, reason=""):
        if self._conn_handle is None:
            return
        try:
            self.ble.gap_disconnect(self._conn_handle)
        except Exception:
            pass

        self._conn_handle = None
        self._svc_start = self._svc_end = None
        self._fff1_val = self._fff2_val = None
        self._cccd_handle = None

        self._svc_done = self._chr_done = self._dsc_done = False

        self.state = self.STATE_IDLE
        self.set_status(3040, "Camera disconnected" + ((" (" + reason + ")") if reason else ""))

    def _save_settings(self):
        # Keep CLB master settings dict in sync, then save via configurator
        self.clb.settings[self.name] = self.settings
        try:
            self.clb.config.save()
        except Exception as e:
            self.events["camera.error"].publish({"error": "save_settings", "detail": str(e)})

