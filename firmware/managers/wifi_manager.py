import network
import time
from managers.base import CLBManager

class Manager(CLBManager):
    version = "1.0.1"
    dependencies = []

    STATE_CONNECTING = "connecting"
    STATE_NOT_CONNECTED = "not connected"
    STATE_ERROR = "error"
    STATE_DISABLED = "disabled"

    def __init__(self,clb):
        super().__init__(clb,defaults={
            "wifissid1": "",
            "wifipwd1": ""
        })
        self.wlan = network.WLAN(network.STA_IF)
        self.connect_start_time = None

    def setup(self, settings):
        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        self.ssid = self.settings.get("wifissid1", "")
        self.password = self.settings.get("wifipwd1", "")

        if not self.ssid or not self.password:
            self.state = self.STATE_ERROR
            self.set_status(2003, "WiFi settings missing")
            return

        try:
            self.wlan.active(True)
            self.wlan.config(pm=0)            
            self.wlan.connect(self.ssid, self.password)
            self.connect_start_time = time.ticks_ms()
            self.state = self.STATE_CONNECTING
            self.set_status(2004, f"Connecting to WiFi SSID: {self.ssid}")
        except Exception as e:
            self.state = self.STATE_ERROR
            self.set_status(2001, f"WiFi connect error: {e}")

    def update(self):
        if not self.enabled:
            return

        if self.state == self.STATE_CONNECTING:
            if self.wlan.isconnected():
                ip = self.wlan.ifconfig()[0]
                self.state = self.STATE_OK
                self.set_status(2000, f"WiFi connected, IP: {ip}")
                time.sleep(0.5)
            elif time.ticks_diff(time.ticks_ms(), self.connect_start_time) > 10000:
                self.state = self.STATE_ERROR
                self.set_status(2001, "WiFi connection timeout")

        elif self.state == self.STATE_OK:
            if not self.wlan.isconnected():
                self.state = self.STATE_NOT_CONNECTED
                self.set_status(2002, "WiFi disconnected")

    def teardown(self):
        try:
            if self.wlan.isconnected():
                self.wlan.disconnect()
            self.wlan.active(False)
            self.set_status(2012, "WiFi radio disabled")
        except Exception as e:
            self.set_status(2013, f"WiFi teardown error: {e}")

    def get_interface(self):
        return {
            "on": ("Enable WiFi", self.command_enable_wifi ),
            "off": ("Disable WiFi manager", self.command_disable_wifi )
        }

    def command_enable_wifi(self):
        self.enabled = True
        self.set_status(2010, "WiFi manually enabled")
        self.setup(self.settings)

    def command_disable_wifi(self):
        self.enabled = False
        self.set_status(2011, "WiFi manually disabled")
        self.teardown()
        self.state = self.STATE_DISABLED
