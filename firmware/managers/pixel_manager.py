from managers.base import CLBManager
import time
import math
import random
import machine
import neopixel
import sys
from graphics.colours import find_random_colour,colour_name_lookup
from graphics.sprite import Sprite
from graphics.text import TextManager
from graphics.light_panel import LightPanel
from graphics.frame import Frame
from graphics.coord_map import CoordMap
from graphics.animations import anim_wandering_sprites,anim_robot_sprites

class Manager(CLBManager):
    version = "1.0.0"
    dependencies = []

    def __init__(self,clb):
        super().__init__(clb,defaults={
            "pixelpin": 18,
            "panel_width": 8,
            "panel_height": 8,
            "x_panels": 3,
            "y_panels": 2,
            "brightness": 1.0,
            "pixeltype": "RGB",
            "animation":"None",
            "panel_type":CoordMap.PIXEL_TYPE_STRING
        })
        self.pixels = None
        self.pixel_count = 0
        self.last_update = time.ticks_ms()
        self.anim_step = 0
        self.clock = None

    def setup(self, settings):

        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        try:
            pin_number = settings["pixelpin"]
            pin = machine.Pin(pin_number, machine.Pin.OUT)
            self.animation = settings["animation"]
            self.clock_active = False

            self.map = CoordMap(
                panel_type=self.settings["panel_type"],
                panel_width=self.settings["panel_width"],
                panel_height=self.settings["panel_height"],
                x_panels=self.settings["x_panels"],
                y_panels=self.settings["y_panels"])

            if self.map.pixels == 0:
                self.state = self.STATE_DISABLED
                self.set_status(4000, "No pixels configured")
                return

            self.pixeltype = self.settings["pixeltype"].upper()

            self.pixels = neopixel.NeoPixel(pin, self.map.pixels)

            self.lightPanel = LightPanel(self.map, self.pixeltype, self.pixels)
            self.lightPanel.clear_col()

            self.frame = Frame(self.lightPanel)

            self.text = TextManager(self.lightPanel)

            self.state = self.STATE_OK

            self.set_status(4001, f"Pixel strip started with {self.map.pixels} pixels")

        except Exception as e:
            self.state = self.STATE_ERROR
            sys.print_exception(e)
            self.set_status(4002, f"Pixel init error: {e}")

    def update(self):

        now = time.ticks_ms()

        if time.ticks_diff(now, self.last_update) > 33:

            if self.animation != "None":
                self.frame.update()
                self.frame.render()

            if self.clock_active == True:
                t = self.clock.time()
                t_str = f"{t[0]:02d}{t[1]:02d}{t[2]:02d}"
                self.text.start_text_display(text=t_str,colour=(100,100,100),steps=2,x=0,y=0,scroll_count=1)
                self.text.update()
                self.text.draw()

            self.lightPanel.show()
            self.last_update = now
        return

    def teardown(self):
        if self.pixels:
            self.pixels = None
            self.set_status(4012, "Pixel manager torn down")

    def get_interface(self):
        return {
            "on": ("Enable pixel animation", self.command_enable),
            "off": ("Disable pixel animation", self.command_disable),
            "test": ("Show test pattern: test", self.command_test),
            "raw_test": ("Show raw pixel: raw_test", self.command_raw_test),
            "fill": ("Fil with colour: fill <r> <g> <b>", self.command_fill_display),
            "set_rgb": ("Set pixel: set_rgb <x> <y> <r> <g> <b>", self.command_set_pixel_rgb),
            "animate": ("Begin animation: animate", self.command_animate),
            "show": ("Show pixels: show",self.command_show),
            "clock": ("Pixel clock",self.command_clock),
            "show_text":("Show text: show_text <x> <y> <r> <g> <b> \"message\"", self.command_show_text)
        }

    def command_enable(self):
        self.enabled = True
        self.set_status(4010, "Pixels manually enabled")
        self.setup(self.settings)

    def command_disable(self):
        self.enabled = False
        self.set_status(4011, "Pixels manually disabled")
        self.state = self.STATE_DISABLED

    def command_test(self):
        print("Testing pixels")
        self.clear()
        for y in range(0,self.map.height):
            for x in range(0,self.map.width):
                self.write_pixel(x,y,(120,255,0))
                self.show()
        print("Pixel Test complete")

    def command_fill_display(self,r,g,b):
        self.lightPanel.clear_rgb(r,g,b)
        self.lightPanel.show()

    def command_set_pixel_rgb(self, x, y, r, g, b):
        self.lightPanel.set_pixel_rgb(x, y, r, g, b)
        self.lightPanel.show()

    def command_show(self):
        self.lightPanel.show()

    def command_clock(self):

        if self.clock==None:
            self.clock = self.get_service_handle("clock")
            if self.clock:
                print("[Pixel] Connected to clock service")
            else:
                print("[Pixel] Clock service unavailable")
                return
        self.clock_active = True

    def command_show_text(self,x=0, y=0, r=100, g=100, b=100,text="hello world"):
        self.text.start_text_display(text=text,colour=(r,g,b),steps=2,x=x,y=y,scroll_count=1)

    def command_animate(self,type):
        if type=="wandering":
            anim_wandering_sprites(self.frame,no_of_sprites=100)
            self.animation="wandering"
        if type=="robot":
            anim_robot_sprites(self.frame)
            self.animation="robot"

    def command_test(self):
        print("Testing pixels")
        self.lightPanel.clear_col()
        for y in range(0,self.map.height):
            for x in range(0,self.map.width):
                self.lightPanel.set_pixel_rgb(x,y,0,20,0)
                self.lightPanel.show()
                time.sleep(0.1)
        print("Pixel Test complete")

    def command_raw_test(self):
        print("Testing pixels with raw addressing")
        self.lightPanel.clear_col()
        for p in range(0,self.map.pixel_bytes,3):
                self.lightPanel.write_col(p,0,20,0)
                self.lightPanel.show()
                time.sleep(0.1)
        print("Pixel Test complete")
