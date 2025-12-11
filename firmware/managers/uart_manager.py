# /managers/uart_manager.py
from managers.base import CLBManager
import machine
import time
from machine import UART

class Manager(CLBManager):
    version = "1.0.1"
    dependencies = []  # Nothing depends on uart yet

    STATE_DISABLED = "disabled"
    STATE_IDLE     = "idle"

    def __init__(self, clb):
        super().__init__(clb, defaults={
            "channel": 0,
            "baud": 9600,
            "bits": 8,
            "parity": "None",
            "stop": 1,
        })
        self.state = self.STATE_IDLE
        self._gen  = None

    # ---------------------------------------------------------------------
    # SETUP
    # ---------------------------------------------------------------------
    def setup(self, settings):
        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        try:
            if (self.settings["parity"].lower() == "even"):
                self.parity = 0
            elif (self.settings["parity"].lower() == "odd"):
                self.parity = 1
            else:
                self.parity = None

            self.channel = self.settings["channel"]
            self.baud = self.settings["baud"]

            self.uart = UART(self.channel, baudrate=self.baud, bits=self.settings["bits"], parity=self.parity, stop=self.settings["stop"]) 


            self.state = self.STATE_OK
            self.set_status(8001, f"UART manager OK on channel {self.channel} at {self.baud} baud")
            self.uart.write('Hello from uart mamanger setup\r\n')

        except Exception as e:
            self.state = self.STATE_DISABLED
            self.set_status(8002, f"UART setup error: {e}")

    # ---------------------------------------------------------------------
    # SAY HELLO
    # ---------------------------------------------------------------------
    def hello(self):
        self.uart.write('Hello from CLB\r\n')
        self.state = self.STATE_OK       # still OK
        self.set_status(8003, "Said hello")

    # ---------------------------------------------------------------------
    # INITIALISE
    # ---------------------------------------------------------------------
    def init(self):
        try:
            if (self.settings["parity"].lower() == "even"):
                self.parity = 0
            elif (self.settings["parity"].lower() == "odd"):
                self.parity = 1
            else:
                self.parity = None

            self.channel = self.settings["channel"]
            self.baud = self.settings["baud"]

            self.uart = UART(self.channel, baudrate=self.baud, bits=self.settings["bits"], parity=self.parity, stop=self.settings["stop"]) 

            self.state = self.STATE_OK
            self.set_status(8001, f"UART initialised on channel {self.channel} at {self.baud} baud")
            self.uart.write('UART initialised\r\n')

        except Exception as e:
            self.state = self.STATE_DISABLED
            self.set_status(8002, f"UART initialization error: {e}")

    # ---------------------------------------------------------------------
    # UPDATE LOOP
    # ---------------------------------------------------------------------
    def update(self):
        if not self.enabled:
            return

        if self._gen:
            try:
                next(self._gen)
            except StopIteration:
                self._gen = None
                self.state = self.STATE_OK


    # ---------------------------------------------------------------------
    # TEARDOWN
    # ---------------------------------------------------------------------
    def teardown(self):
        self.uart.deinit()
        self.set_status(8005, "UART manager torn down")

    # ---------------------------------------------------------------------
    # COMMAND INTERFACE
    # ---------------------------------------------------------------------
    def get_interface(self):
        return {
            "hello": ("Say hello", self.cmd_hello),
            "init": ("UART initialising", self.cmd_init)
        }

    def cmd_hello(self):
        self.hello()

    def cmd_init(self):
        self.init()
