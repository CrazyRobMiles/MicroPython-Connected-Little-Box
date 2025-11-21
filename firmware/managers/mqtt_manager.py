from managers.base import CLBManager
from umqtt.simple import MQTTClient
import time
import machine

class Manager(CLBManager):
    version = "1.5.0"
    dependencies = ["wifi"]

    STATE_CONNECTING = "connecting"

    def __init__(self, clb):
        uid = machine.unique_id().hex().upper()
        default_name = f"CLB-{uid}"

        # Only essential, persistable settings
        super().__init__(clb, defaults={
            "mqtthost": "",
            "mqttport": 1883,
            "mqttuser": "",
            "mqttpwd": "",
            "mqttsecure": "no",

            # Editable box name (used for addressing)
            "devicename": default_name,

            # Namespace for all CLB messaging
            "topicbase": "clb"
        })

        self.client = None
        self.last_loop_time = 0
        self.dependency_instances = []

    # ---------------------------------------------------------------------
    # SETUP
    # ---------------------------------------------------------------------

    def setup(self, settings):
        super().setup(settings)
        if not self.enabled:
            self.state = self.STATE_ERROR
            return

        self.host = self.settings["mqtthost"]
        self.port = int(self.settings["mqttport"])
        self.username = self.settings["mqttuser"]
        self.password = self.settings["mqttpwd"]
        self.devicename = self.settings["devicename"]
        self.topicbase = self.settings["topicbase"]

        self.topic_receive = f"{self.topicbase}/{self.devicename}"

        print(f"Listening on:{self.topic_receive}")

        if not self.host:
            self.state = self.STATE_ERROR
            self.set_status(3000, "MQTT disabled: no host configured")
            return

        self.state = self.STATE_WAITING
        self.set_status(3001, "Waiting for WiFi to connect MQTT")

    # ---------------------------------------------------------------------
    # UPDATE LOOP
    # ---------------------------------------------------------------------

    def unresolved_dependencies(self):
        return [
            m for m in self.dependency_instances
            if not hasattr(m, "state") or m.state not in ("connected", "OK", "ok")
        ]

    def update(self):
        if not self.enabled:
            return

        # Wait for WiFi manager to report OK
        if self.state == self.STATE_WAITING:
            if self.unresolved_dependencies():
                return
            self.state = self.STATE_CONNECTING

        # Connect to MQTT
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
                self.client.set_callback(self._on_message)
                self.client.connect()

                # Subscribe to our own box's command topic
                self.client.subscribe(self.topic_receive)
                self.set_status(3008, f"Subscribed to {self.topic_receive}")

                self.state = self.STATE_OK
                self.set_status(3003, f"MQTT connected as {self.devicename}")

            except Exception as e:
                self.state = self.STATE_ERROR
                self.set_status(3004, f"MQTT connection failed: {e}")
                return

        # Handle incoming messages occasionally
        if self.state == self.STATE_OK:
            if time.ticks_diff(time.ticks_ms(), self.last_loop_time) > 250:
                try:
                    self.client.check_msg()
                except Exception as e:
                    self.state = self.STATE_ERROR
                    self.set_status(3005, f"MQTT connection lost: {e}")
                self.last_loop_time = time.ticks_ms()

    # ---------------------------------------------------------------------
    # MQTT MESSAGE HANDLER
    # ---------------------------------------------------------------------

    def _on_message(self, topic, msg):
        topic = topic.decode()
        data  = msg.decode()

        self.set_status(3014, f"Message on {topic}: {data}")

        if topic == self.topic_receive:
            try:
                # Run incoming message as console command
                self.clb.handle_command(data)
            except Exception as e:
                self.set_status(3015, f"Command error: {e}")

    # ---------------------------------------------------------------------
    # CLEAN TEARDOWN
    # ---------------------------------------------------------------------

    def teardown(self):
        if self.client:
            try:
                self.client.disconnect()
            except Exception as e:
                self.set_status(3016, f"Error disconnecting: {e}")
        self.client = None
        self.set_status(3017, "MQTT manager shut down")

    # ---------------------------------------------------------------------
    # PUBLIC COMMAND INTERFACE
    # ---------------------------------------------------------------------

    def get_interface(self):
        return {
            "on":   ("Enable MQTT manager", self.command_enable),
            "off":  ("Disable MQTT manager", self.command_disable),
            "send": ("send <box> <msg> — send a command to another box",
                     self.command_send),
        }

    def command_enable(self):
        self.enabled = True
        self.set_status(3018, "MQTT manually enabled")
        self.setup(self.settings)

    def command_disable(self):
        self.enabled = False
        self.state = self.STATE_DISABLED
        self.teardown()
        self.set_status(3019, "MQTT manually disabled")

    # ---------------------------------------------------------------------
    # SEND A COMMAND TO ANOTHER BOX
    # ---------------------------------------------------------------------

    def command_send(self, target_box_name, message):
        """
        Publish a command to another CLB box.
        Example:
            mqtt.send hallway "pixel.fill 255 0 0"
        """

        if not self.client:
            self.set_status(3020, "MQTT not connected")
            return

        if not target_box_name:
            self.set_status(3021, "No box name specified")
            return

        # Target topic: clb/<target_box_name>
        topic = f"{self.topicbase}/{target_box_name}"

        try:
            self.client.publish(topic, message)
            self.set_status(3022, f"Sent to {topic}")
        except Exception as e:
            self.set_status(3023, f"MQTT send error: {e}")
