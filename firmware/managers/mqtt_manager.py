# /managers/mqtt_manager.py
from managers.base import CLBManager
from managers.event import Event
from umqtt.simple import MQTTClient
import time
import machine

class Manager(CLBManager):
    version = "2.0.0"
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
            "topicbase": "lb/data"
        })

        # --- FIXED EVENT SET (mirrors approach in clock_manager) ---
        self.events = {
            "mqtt.connected":    Event("mqtt.connected",    "MQTT connection established", self),
            "mqtt.disconnected": Event("mqtt.disconnected", "MQTT connection lost",        self),
            "mqtt.message":      Event("mqtt.message",      "Any MQTT message received",   self),
            # Topic-specific events are *not* dynamically generated.
            # OTA managers should filter themselves inside the handler.
        }

        self.client = None
        self.last_loop_time = 0
        self.dependency_instances = []

    # ---------------------------------------------------------------------
    # SETUP
    # ---------------------------------------------------------------------
    def setup(self, settings):
        super().setup(settings)
        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        self.host = self.settings["mqtthost"]
        self.port = int(self.settings["mqttport"])
        self.username = self.settings["mqttuser"]
        self.password = self.settings["mqttpwd"]
        self.devicename = self.settings["devicename"]
        self.topicbase = self.settings["topicbase"]

        self.topic_receive = f"{self.topicbase}/{self.devicename}"
        print(f"[MQTT] Listening on: {self.topic_receive}")

        if not self.host:
            self.state = self.STATE_ERROR
            self.set_status(3000, "MQTT disabled: no host configured")
            return

        self.state = self.STATE_WAITING
        self.set_status(3001, "MQTT waiting for WiFi")

    # ---------------------------------------------------------------------
    # UPDATE LOOP
    # ---------------------------------------------------------------------
    def unresolved_dependencies(self):
        return [
            m for m in self.dependency_instances
            if not hasattr(m, "state") or m.state not in ("ok", "connected", "OK")
        ]

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
                self.client = MQTTClient(
                    client_id=self.devicename,
                    server=self.host,
                    port=self.port,
                    user=self.username or None,
                    password=self.password or None,
                    ssl=False
                )
                self.client.set_callback(self._on_mqtt)
                self.client.connect()

                # Subscribe to own topic
                self.client.subscribe(self.topic_receive)
                self.set_status(3008, f"Subscribed to {self.topic_receive}")

                self.state = self.STATE_OK
                self.set_status(3003, f"MQTT connected as {self.devicename}")

                # --- FIRE EVENT ---
                self.events["mqtt.connected"].publish({"device": self.devicename})

            except Exception as e:
                self.state = self.STATE_ERROR
                self.set_status(3004, f"MQTT connection failed: {e}")
                self.events["mqtt.disconnected"].publish({"error": str(e)})
                return

        # Check for messages
        if self.state == self.STATE_OK:
            if time.ticks_diff(time.ticks_ms(), self.last_loop_time) > 250:
                try:
                    self.client.check_msg()
                except Exception as e:
                    self.state = self.STATE_ERROR
                    self.set_status(3005, f"MQTT lost: {e}")
                    self.events["mqtt.disconnected"].publish({"error": str(e)})
                self.last_loop_time = time.ticks_ms()

    # ---------------------------------------------------------------------
    # MQTT CALLBACK
    # ---------------------------------------------------------------------
    def _on_mqtt(self, topic, msg):
        topic = topic.decode()
        payload = msg.decode()

        # --- FIRE GENERIC MQTT MESSAGE EVENT ---
        self.events["mqtt.message"].publish({
            "topic": topic,
            "payload": payload
        })

        # Treat messages on own topic as remote console commands
        if topic == self.topic_receive:
            try:
                self.clb.handle_command(payload)
            except Exception as e:
                self.set_status(3015, f"Command error: {e}")

    # ---------------------------------------------------------------------
    # SHUTDOWN
    # ---------------------------------------------------------------------
    def teardown(self):
        if self.client:
            try:
                self.client.disconnect()
            except Exception:
                pass
        self.client = None
        self.events["mqtt.disconnected"].publish({"error": "shutdown"})
        self.set_status(3017, "MQTT manager shut down")

    # ---------------------------------------------------------------------
    # COMMAND INTERFACE
    # ---------------------------------------------------------------------
    def get_interface(self):
        return {
            "on":   ("Enable MQTT", self.command_enable),
            "off":  ("Disable MQTT", self.command_disable),
            "send": ("send <box> <cmd>", self.command_send)
        }

    def command_enable(self):
        self.enabled = True
        self.setup(self.settings)
        self.set_status(3018, "MQTT manually enabled")

    def command_disable(self):
        self.enabled = False
        self.state = self.STATE_DISABLED
        self.teardown()
        self.set_status(3019, "MQTT manually disabled")

    def command_send(self, target, message):
        if not self.client:
            self.set_status(3020, "MQTT not connected")
            return

        topic = f"{self.topicbase}/{target}"
        try:
            self.client.publish(topic, message)
            self.set_status(3022, f"Sent to {topic}")
        except Exception as e:
            self.set_status(3023, f"MQTT send error: {e}")
