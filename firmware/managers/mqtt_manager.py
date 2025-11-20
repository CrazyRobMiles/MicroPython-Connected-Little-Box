from managers.base import CLBManager
from umqtt.simple import MQTTClient
import time
import machine

class Manager(CLBManager):
    version = "1.1.0"
    dependencies = ["wifi"]

    STATE_CONNECTING = "connecting"
    STATE_WAITING = "waiting"
    STATE_ERROR = "error"

    def __init__(self,clb):
        device_id = machine.unique_id().hex().upper()
        device_name = f"CLB-{device_id}"

        super().__init__(clb,defaults={
            "mqtthost": "",
            "mqttport": 1883,
            "mqttuser": "",
            "mqttpwd": "",
            "devicename": device_name
        })
        self.client = None
        self.last_loop_time = 0

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

        if not self.host:
            self.state = self.STATE_ERROR
            self.set_status(3000, "MQTT disabled (no host)")
            return

        self.state = self.STATE_WAITING
        self.set_status(3001, "MQTT attempting connection")

    def update(self):
        if not self.enabled:
            return

        if self.state==self.STATE_WAITING:
            waiting_on = self.unresolved_dependencies()
            if waiting_on:
                return
            else:
                self.state = self.STATE_CONNECTING

        if self.state == self.STATE_CONNECTING:
            try:
                self.client = MQTTClient(
                    client_id=self.devicename,
                    server=self.host,
                    port=self.port,
                    user=self.username or None,
                    password=self.password or None,
                    ssl=False  # Pico W umqtt.simple doesn't support SSL
                )
                self.client.set_callback(self._on_message)
                self.client.connect()
                ping_topic = f"lb/connected"
                self.client.subscribe(ping_topic)
                self.set_status(3007, f"Subscribed to {ping_topic}")
                self.state = self.STATE_OK
                self.set_status(3003, "MQTT connected")
            except Exception as e:
                self.state = self.STATE_ERROR
                self.set_status(3004, f"MQTT connect error: {e}")

        if self.state == self.STATE_OK:
            # Only check for new messages every 500ms to avoid blocking
            if time.ticks_diff(time.ticks_ms(), self.last_loop_time) > 500:
                try:
                    self.client.check_msg()  # non-blocking
                except Exception as e:
                    self.state = self.STATE_ERROR
                    self.set_status(3005, f"MQTT lost: {e}")
                self.last_loop_time = time.ticks_ms()

    def _on_message(self, topic, msg):
        self.set_status(3014, f"Received on {topic.decode()}: {msg.decode()}")

    def teardown(self):
        if self.client:
            try:
                self.client.disconnect()
            except Exception as e:
                self.set_status(3012, f"MQTT disconnect error: {e}")
            self.client = None
        self.set_status(3013, "MQTT manager torn down")

    def get_interface(self):
        return {
            "on": ("Enable MQTT manager", self.command_enable),
            "off": ("Disable MQTT manager", self.command_disable),
            "ping": ("Send a test message to the device topic", self.command_test_message)
        }

    def get_commands(self):
        return [
        ]

    def command_enable(self):
        self.enabled = True
        self.set_status(3010, "MQTT manually enabled")
        self.setup(self.settings)

    def command_disable(self):
        self.enabled = False
        self.set_status(3011, "MQTT manually disabled")
        self.teardown()
        self.state = self.STATE_ERROR

    def command_test_message(self):
        if self.client:
            topic = f"lb/connected"
            try:
                self.client.publish(topic, "Hello from CLB")
                self.set_status(3015, f"Test message sent to {topic}")
            except Exception as e:
                self.set_status(3016, f"MQTT publish failed: {e}")
        else:
            self.set_status(3017, "MQTT client not connected")
