# managers/mqtt_manager.py
#
# MQTT manager with byte-range file transfer and configurable filebase.
#
# Protocol:
#   Requests published to:  <filebase>/fetch
#   Responses published to: <filebase>/result
#
# Request payload:
#   {"file": "path", "start": <byte offset>, "length": <max bytes>}
#
# Response payload:
#   {"file": "path", "start": ..., "length": ..., "size": ..., "data": "<b64>", "eof": bool}
#
# Client performs sequential requests until eof == True.
#
# Server responds to ANY file request for which it has the file.
#

from managers.base import CLBManager
from managers.event import Event
import machine, os, json, time

try:
    import ubinascii
except ImportError:
    ubinascii = None


DEFAULT_RANGE_SIZE = 2000     # number of bytes client asks for in each request
FETCH_TIMEOUT_MS = 5000        # how long we wait for a response
FETCH_REQUEST_RETRY_INTERVAL_MS = 1000

class Manager(CLBManager):
    version = "4.0.1"
    dependencies = ["wifi"]

    STATE_WAITING = "waiting"
    STATE_CONNECTING = "connecting"

    def __init__(self, clb):
        uid = machine.unique_id().hex().upper()
        default_name = f"CLB-{uid}"

        super().__init__(clb, defaults={
            "mqtthost": "",
            "mqttport": 1883,
            "mqttuser": "",
            "mqttpwd": "",
            "mqttsecure": "no",
            "devicename": default_name,
            "topicbase": "lb/data",
            "filebase": "lb/file"
        })

        self.client = None
        self.last_loop_time = 0

        # Active download state
        self._fetch = None
        self._fetch_active = False

        # Events
        self.events = {
            "mqtt.connected":      Event("mqtt.connected", "MQTT connected", self),
            "mqtt.disconnected":   Event("mqtt.disconnected", "MQTT disconnected", self),
            "mqtt.message":        Event("mqtt.message", "Raw MQTT message", self),

            # Server-side events
            "file.request":        Event("file.request", "File range request received", self),
            "file.range_sent":     Event("file.range_sent", "File range served", self),
            "file.range_error":    Event("file.range_error", "Error serving range", self),

            # Client-side fetch events
            "file.fetch_started":  Event("file.fetch_started", "Fetch started", self),
            "file.fetch_range":    Event("file.fetch_range", "Received file range", self),
            "file.fetch_complete": Event("file.fetch_complete", "Fetch complete", self),
            "file.fetch_error":    Event("file.fetch_error", "Fetch error", self),
        }

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------
    def _b64encode(self, data):
        if not data:
            return ""
        return ubinascii.b2a_base64(data).decode().strip()

    def _b64decode(self, s):
        if not s:
            return b""
        return ubinascii.a2b_base64(s)

    def _ensure_dir_for(self, file_path):
        # ensure parent directories exist
        parts = file_path.split("/")
        cur = ""
        for p in parts[:-1]:
            if not p:
                continue
            cur = p if not cur else cur + "/" + p
            try:
                os.stat(cur)
            except:
                try:
                    os.mkdir(cur)
                except:
                    pass

    # ---------------------------------------------------------------
    # Setup
    # ---------------------------------------------------------------
    def setup(self, settings):
        super().setup(settings)

        self.mqtthost = settings["mqtthost"]
        self.mqttport = int(settings["mqttport"])
        self.mqttuser = settings["mqttuser"]
        self.mqttpwd = settings["mqttpwd"]
        self.devicename = settings["devicename"]
        self.topicbase = settings["topicbase"]
        self.filebase = settings["filebase"]

        if not self.mqtthost:
            self.state = self.STATE_ERROR
            return

        self.state = self.STATE_WAITING

    def unresolved_dependencies(self):
        return [
            m for m in self.dependency_instances
            if not hasattr(m, "state") or m.state not in ("connected", "OK", "ok")
        ]

    # ---------------------------------------------------------------
    # Main update loop
    # ---------------------------------------------------------------
    def update(self):
        if not self.enabled:
            return

        # Wait for WiFi
        if self.state == self.STATE_WAITING:
            if self.unresolved_dependencies():
                return
            self.state = self.STATE_CONNECTING

        # Connect
        if self.state == self.STATE_CONNECTING:
            try:
                from umqtt.simple import MQTTClient
                self.client = MQTTClient(
                    client_id=self.devicename,
                    server=self.mqtthost,
                    port=self.mqttport,
                    user=self.mqttuser or None,
                    password=self.mqttpwd or None,
                    ssl=False
                )
                self.client.set_callback(self._on_mqtt)
                self.client.connect()

                # Subscribe to incoming commands
                self.client.subscribe(f"{self.topicbase}/{self.devicename}")

                # Subscribe to global file transfer topics
                self.client.subscribe(f"{self.filebase}/{self.devicename}/fetch")
                self.client.subscribe(f"{self.filebase}/{self.devicename}/result")

                self.events["mqtt.connected"].publish({"device": self.devicename})
                self.state = self.STATE_OK

            except Exception as e:
                self.events["mqtt.disconnected"].publish({"error": str(e)})
                self.state = self.STATE_ERROR
                return

        # Poll messages
        if self.state == self.STATE_OK:
            if time.ticks_diff(time.ticks_ms(), self.last_loop_time) > 200:
                try:
                    self.client.check_msg()
                except Exception as e:
                    self.events["mqtt.disconnected"].publish({"error": str(e)})
                    self.state = self.STATE_ERROR
                self.last_loop_time = time.ticks_ms()

        # Drive active fetch state-machine
        if self._fetch_active:
            self._update_fetch()

    # ---------------------------------------------------------------
    # MQTT callback
    # ---------------------------------------------------------------
    def _on_mqtt(self, topic, message):
        topic = topic.decode()
        try:
            payload = json.loads(message.decode())
        except:
            payload = None

        self.events["mqtt.message"].publish({"topic": topic, "payload": payload})

        # Routing
        if topic == f"{self.topicbase}/{self.devicename}":
            # CLI command routing
            try:
                self.clb.handle_command(message.decode())
            except:
                pass
            return

        if topic == f"{self.filebase}/{self.devicename}/fetch":
            self._handle_range_request(payload)
            return

        if topic == f"{self.filebase}/{self.devicename}/result":
            self._handle_range_response(payload)
            return

    # ---------------------------------------------------------------
    # SERVER-SIDE RANGE SERVING
    # ---------------------------------------------------------------
    def _handle_range_request(self, payload):
        if not payload:
            return
        if "file" not in payload:
            return
        if "start" not in payload or "length" not in payload:
            return

        file_path = payload["file"]
        start = int(payload["start"])
        length = int(payload["length"])

        self.events["file.request"].publish({
            "file": file_path,
            "start": start,
            "length": length
        })

        try:
            with open(file_path, "rb") as fp:
                fp.seek(start)
                data = fp.read(length) or b""

            response = {
                "file": file_path,
                "start": start,
                "length": length,
                "size": len(data),
                "data": self._b64encode(data),
                "eof": (len(data) < length)
            }

            self.publish(f"{self.filebase}/{self.devicename}/result", response)
            self.events["file.range_sent"].publish(response)

        except Exception as e:
            response = {
                "file": file_path,
                "start": start,
                "length": length,
                "size": 0,
                "data": "",
                "eof": True,
                "error": str(e)
            }
            self.publish(f"{self.filebase}/result", response)
            self.events["file.range_error"].publish(response)

    # ---------------------------------------------------------------
    # CLIENT-SIDE RANGE HANDLING
    # ---------------------------------------------------------------
    def fetch_file(self, filename, dest_path=None, range_size=DEFAULT_RANGE_SIZE,source=None):
        if self._fetch_active:
            self.events["file.fetch_error"].publish({"file": filename, "error": "busy"})
            return False

        if dest_path is None:
            dest_path = filename

        self._ensure_dir_for(dest_path)

        try:
            fp = open(dest_path, "wb")
        except Exception as e:
            self.events["file.fetch_error"].publish({"file": filename, "error": str(e)})
            return False

        self._fetch = {
            "file": filename,
            "dest": dest_path,
            "fp": fp,
            "pos": 0,
            "range": range_size,
            "last": time.ticks_ms(),
            "timeout": FETCH_TIMEOUT_MS,
            "source":source, # None=server
            "retry": FETCH_REQUEST_RETRY_INTERVAL_MS,
            "starting": True
        }

        self._fetch_active = True
        self.events["file.fetch_started"].publish({
            "file": filename,
            "dest": dest_path,
            "range": range_size
        })

        print(f"MQTT file fetch started. File:{filename} Dest:{dest_path}")

        return True

    def _update_fetch(self):

        f = self._fetch

        now = time.ticks_ms()
        gap = time.ticks_diff(now, f["last"])

        # Timeout?
        if gap > f["timeout"]:
            self._end_fetch_error("timeout")
            return

        # Request?
        if gap > f["retry"] or f["starting"]:
            f["starting"]= False

            # Determine target topic

            if f["source"] is None:
                topic = f"{self.filebase}/fetch"
            else:
                topic = f"{self.filebase}/fetch/{f['source']}"

            # Issue next range request
            print(f"Requesting chunk of {f["file"]} pos {f["pos"]} range {f["range"]} ")

            self.publish(topic, {
                "file": f["file"],
                "start": f["pos"],
                "length": f["range"],
                "device": self.devicename
            })

            f["last"] = now

    def _handle_range_response(self, frame):
        if not self._fetch_active:
            return

        f = self._fetch

        if frame.get("file") != f["file"]:
            print("No file")
            return

        if frame.get("start") != f["pos"]:
            print("Bad range")
            return  # not our expected range

        if "error" in frame:
            print(f"Got error:{frame["error"]}")
            self._end_fetch_error(frame["error"])
            return

        raw = self._b64decode(frame.get("data", ""))
        size = frame.get("size", 0)

        try:
            f["fp"].write(raw)
        except Exception as e:
            print("Bad write")
            self._end_fetch_error("write: " + str(e))
            return

        f["pos"] += size

        self.events["file.fetch_range"].publish({
            "file": f["file"],
            "start": frame["start"],
            "size": size,
            "total": f["pos"],
            "eof": frame.get("eof", False)
        })

        if frame.get("eof"):
            print("All good")
            self._end_fetch_success()

    def _end_fetch_error(self, reason):
        f = self._fetch
        try:
            f["fp"].close()
        except:
            pass

        self._fetch = None
        self._fetch_active = False

        self.events["file.fetch_error"].publish({
            "file": f.get("file"),
            "dest": f.get("dest"),
            "reason": reason
        })

    def _end_fetch_success(self):
        f = self._fetch
        try:
            f["fp"].close()
        except:
            pass

        info = {
            "file": f["file"],
            "dest": f["dest"],
            "bytes": f["pos"]
        }

        self._fetch = None
        self._fetch_active = False

        self.events["file.fetch_complete"].publish(info)

    # ---------------------------------------------------------------
    # Interface Wrappers
    # ---------------------------------------------------------------
    def get_interface(self):
        return {
            "name":         ("Return device name", self.command_name),
            "send":         ("send <box> <msg>", self.command_send),

            # File-transfer API
            "fetch_file":   ("fetch_file <file> [dest] [range]", self.command_fetch_file),
            "fetch_status": ("Fetch status", self.command_fetch_status),
        }

    def command_name(self):
        return self.devicename

    def command_send(self, target, msg):
        self.publish(f"{self.topicbase}/{target}", msg)

    def command_fetch_file(self, filename, dest=None, range_size=DEFAULT_RANGE_SIZE,source=None):
        return self.fetch_file(filename, dest, int(range_size),source)

    def command_fetch_status(self):
        return self._fetch

    # ---------------------------------------------------------------
    # Publishing helper
    # ---------------------------------------------------------------
    def publish(self, topic, payload):
        print(f"Publishing {payload} to {topic}")
        if self.client:
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            self.client.publish(topic, payload)

    # ---------------------------------------------------------------
    # Teardown
    # ---------------------------------------------------------------
    def teardown(self):
        if self._fetch and self._fetch.get("fp"):
            try:
                self._fetch["fp"].close()
            except:
                pass

        self._fetch = None
        self._fetch_active = False

        if self.client:
            try:
                self.client.disconnect()
            except:
                pass
            self.client = None
