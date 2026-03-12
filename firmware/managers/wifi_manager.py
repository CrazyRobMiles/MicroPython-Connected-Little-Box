import network
import time
from managers.base_manager import CLBManager

class Manager(CLBManager):
    version = "1.0.2"   # bumped to indicate retry behaviour added

    STATE_CONNECTING = "connecting"
    STATE_NOT_CONNECTED = "not connected"
    STATE_ERROR = "error"
    STATE_DISABLED = "disabled"

    def __init__(self,clb):
        # add retry interval to defaults so it can be configured
        super().__init__(clb,defaults={
            "wifissid1": "",
            "wifipwd1": "",
            "retry_interval_ms": 30000  # how long to wait before retrying
        })
        self.wlan = network.WLAN(network.STA_IF)
        self.connect_start_time = None
        self.last_attempt = None
        self.retry_interval_ms = 30000
        
    def _get_credentials(self):
        self.ssid = self.settings.get("wifissid1", "")
        self.password = self.settings.get("wifipwd1", "")
        self.retry_interval_ms = int(self.settings.get("retry_interval_ms", 30000))

    def setup(self, settings):
        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        self._get_credentials()

        # reset retry state so that update() will attempt immediately
        self.last_attempt = None

        if not self.ssid or not self.password:
            self.state = self.STATE_ERROR
            self.set_status(2003, "WiFi settings missing")
            return

        # kick off first connection try
        self._attempt_connect()

    def _attempt_connect(self):
        """Begin a connection attempt and record timestamps."""
        try:
            self._get_credentials()
            self.wlan.active(True)
            self.wlan.config(pm=0)
            self.wlan.connect(self.ssid, self.password)
            self.connect_start_time = time.ticks_ms()
            self.last_attempt = self.connect_start_time
            self.state = self.STATE_CONNECTING
            self.set_status(2004, f"Connecting to WiFi SSID: {self.ssid}")
        except Exception as e:
            self.state = self.STATE_ERROR
            self.set_status(2001, f"WiFi connect error: {e}")

    def update(self):
        if not self.enabled:
            return

        now = time.ticks_ms()

        if self.state == self.STATE_CONNECTING:
            if self.wlan.isconnected():
                ip = self.wlan.ifconfig()[0]
                self.state = self.STATE_OK
                self.set_status(2000, f"WiFi connected, IP: {ip}")
                time.sleep(0.5)
            elif time.ticks_diff(now, self.connect_start_time) > 10000:
                # connection attempt timed out; move to error state and allow retry
                self.state = self.STATE_ERROR
                self.set_status(2001, "WiFi connection timeout")

        elif self.state == self.STATE_OK:
            if not self.wlan.isconnected():
                self.state = self.STATE_NOT_CONNECTED
                self.set_status(2002, "WiFi disconnected")

        # if we're currently errored or not connected, check whether it's
        # time to try again
        elif self.state in (self.STATE_ERROR, self.STATE_NOT_CONNECTED):
            # don't attempt if we don't have credentials
            self._get_credentials()
            if self.ssid and self.password:
                if self.last_attempt is None or time.ticks_diff(now, self.last_attempt) > self.retry_interval_ms:
                    self.set_status(2005, "Retrying WiFi connection")
                    self._attempt_connect()

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
        # re-run setup so that credentials and retry interval are re-read
        # and first connect is attempted immediately
        self.setup(self.settings)

    def command_disable_wifi(self):
        self.enabled = False
        self.set_status(2011, "WiFi manually disabled")
        self.teardown()
        self.state = self.STATE_DISABLED
