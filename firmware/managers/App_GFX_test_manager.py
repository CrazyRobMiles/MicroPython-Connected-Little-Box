# /managers/display_manager.py
from managers.base_manager import CLBManager
from managers.event import Event
from graphics.display_devices import GFX_LCDDisplay, DisplayItem
import sys

# --------------------------------------------------------------------
# CLB Manager
# --------------------------------------------------------------------

class Manager(CLBManager):
    version = "1.0.2"


    def __init__(self, clb):
        super().__init__(clb, defaults={
            "enabled": True,
        })

        self.display = None
        self.items = {}        # holds DisplayItem objects for other managers

        self.events = {
            "display.updated": Event("display.updated",
                                     "Display updated", self)
        }

    # ----------------------------------------------------------------
    # SETUP
    # ----------------------------------------------------------------
    def setup(self, settings):

        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        self.display = GFX_LCDDisplay()
        
        self.display.text("Simple text display",0,0,1)
        
        item = self.display.get_display_item(0,20,60,20,DisplayItem.LEFT,15,0,"bitmap14_outline",1)
        
        print("kaboom?")
        
        item.do_display("kaboom")
        
        self.display.update()

    def setup_services(self):
        
        button_A_pressed = self.clb.get_event("gpio.A_low")
        
        if button_A_pressed:
            print("Event handler bound")
            button_A_pressed.subscribe(self.on_button_A_pressed)
            
        button_A_released = self.clb.get_event("gpio.A_high")
        
        if button_A_released:
            print("Event handler bound")
            button_A_released.subscribe(self.on_button_A_released)
    # ----------------------------------------------------------------
    # UPDATE LOOP
    # ----------------------------------------------------------------
    def update(self):
        if not self.enabled or not self.display:
            return


    def on_button_A_pressed(self,event,data):
        print("A pressed")

    def on_button_A_released(self,event,data):
        print("A released")

    # ----------------------------------------------------------------
    # COMMAND INTERFACE
    # ----------------------------------------------------------------
    def get_interface(self):
        return {
            "clear": ("Clear screen", self.cmd_clear),
            "text": ("Display text: text <x> <y> <msg>", self.cmd_text),
            "update": ("Force update", self.cmd_update),
        }

    def cmd_clear(self):
        if self.display:
            self.display.clear()
            self.display.update()

    def cmd_text(self, x, y, msg):
        if not self.display:
            return
        x, y = int(x), int(y)
        self.display.text(msg, x, y, scale=self.settings["text_scale"])
        self.display.update()

    def cmd_update(self):
        if self.display:
            self.display.update()
