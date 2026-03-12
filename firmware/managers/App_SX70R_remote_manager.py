# /managers/display_manager.py
from managers.base_manager import CLBManager
from managers.event import Event
from graphics.display_devices import Ht16k33_14Seg, DisplayItem
import sys
import time

# --------------------------------------------------------------------
# CLB Manager
# --------------------------------------------------------------------

class Manager(CLBManager):
    version = "1.0.1"

    def __init__(self, clb):
        super().__init__(clb, defaults={
            "enabled": True,
            "i2c_sda": 0,
            "i2c_clk": 1
        })

        self.display = None
        self.events = {}
        self.camera_ready = False
        self.display_stack = []
        
        self.shutter_speeds = [
            ("Auto", 2),
            ("+32",32000),
            ("+16",16000),
            ("+8",8000),
            ("+2",2000),
            ("+1",1000),
            ("2",1000/2),
            ("4",1000/4),
            ("8",1000/8),
            ("15",1000/15),
            ("30",1000/30),
            ("60",1000/60),
            ("120",1000/120),
            ("250",1000/250)
        ]
        self.speed_pos = 11 # 60th of a second

        self.shutter_delays = [
            ("D  0", 0),
            ("D  2", 2),
            ("D  5", 5),
            ("D 10", 10)
        ]
        
        self.delay_pos = 0 # no delay
        
        self.showing_speed = True
        self.counting_down = False
        self.countdown_start_time = None
        
    # ----------------------------------------------------------------
    # SETUP
    # ----------------------------------------------------------------
    
    def setup(self, settings):

        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        i2c_sda = self.settings.get("i2c_sda", 0)
        i2c_clk = self.settings.get("i2c_clk", 1)

        self.set_i2c(i2c_sda,i2c_clk)
        
        self.display = Ht16k33_14Seg(self)
        
        self.display.text("On")
        self.display.update()
        
    def setup_services(self):
        
        shutter_pressed = self.clb.get_event("gpio.Shutter_low")
        
        shutter_pressed.subscribe(self.on_shutter_pressed)
            
        exposure_cw_event = self.clb.get_event("rotary_encoder.exposure_moved_clockwise")
        exposure_cw_event.subscribe(self.on_exposure_clockwise)

        exposure_acw_event = self.clb.get_event("rotary_encoder.exposure_moved_anticlockwise")
        exposure_acw_event.subscribe(self.on_exposure_anticlockwise)
            
        rotary_pressed  = self.clb.get_event("rotary_encoder.exposure_button_pressed")
        rotary_pressed.subscribe(self.on_rotary_button_pressed)
        
        camera_connected  = self.clb.get_event("camera.connected")
        camera_connected.subscribe(self.on_camera_connected)
        
        camera_disconnected  = self.clb.get_event("camera.disconnected")
        camera_disconnected.subscribe(self.on_camera_disconnected)
        
        exposure_finished  = self.clb.get_event("camera.exposure_finished")
        exposure_finished.subscribe(self.on_exposure_finished)
        
        self.camera = self.get_service_handle("sx70r")
        
        self.display.text("Wait")
        self.display.update()
        
    def fire_shutter(self):
        if not self.camera_ready:
            self.display.text("Wait")
        else:
            self.display.text("Fire")
            self.display.update()
            text,v = self.shutter_speeds[self.speed_pos]
            hex=f"{int(v):0{4}x}"
            command="FFFF"+hex
            self.camera.fire_shutter(command)
            
        self.display.update()
        
    def on_shutter_pressed(self,event,data):
        if self.delay_pos==0:
            self.fire_shutter()
        else:
            self.counting_down=True
            self.countdown_start_time = time.ticks_ms()
            text,v = self.shutter_delays[self.delay_pos]
            self.seconds_left = v
            
    def display_status(self):
        if not self.camera_ready:
            text="Wait"
        else:
            if self.counting_down:
                text=str(self.seconds_left)
            else:
                if self.showing_speed:
                    text,v = self.shutter_speeds[self.speed_pos]
                else:
                    text,v = self.shutter_delays[self.delay_pos]
        self.display.text(text)
        self.display.update()

    def on_exposure_clockwise(self,event,data):
        if self.counting_down:
            return
        
        if self.showing_speed:
            self.speed_pos =  self.speed_pos-1
            if self.speed_pos <0:
                self.speed_pos = len(self.shutter_speeds)-1
        else:
            self.delay_pos =  self.delay_pos-1
            if self.delay_pos <0:
                self.delay_pos = len(self.shutter_delays)-1
            
        self.display_status()

    def on_exposure_anticlockwise(self,event,data):
        if self.counting_down:
            return
        
        if self.showing_speed:
            self.speed_pos =  self.speed_pos+1
            if self.speed_pos == len(self.shutter_speeds):
                self.speed_pos = 0
        else:
            self.delay_pos =  self.delay_pos+1
            if self.delay_pos == len(self.shutter_delays):
                self.delay_pos = 0
            
        self.display_status()

    def on_rotary_button_pressed(self,event,data):
        if self.counting_down:
            self.counting_down=False
        else:
            if self.showing_speed:
                self.showing_speed=False
            else:
                self.showing_speed=True

        self.display_status()
        
    def on_camera_connected(self,event,data):
        self.camera_ready = True
        self.display_status()
       
    def on_camera_disconnected(self,event,data):
        self.camera_ready = False
        self.display_status()

    def on_exposure_finished(self,event,data):
        self.display_status()

    # ----------------------------------------------------------------
    # UPDATE LOOP
    # ----------------------------------------------------------------
    def update(self):
        if self.counting_down:
            if self.camera_ready == False:
                self.counting_down=False
                self.display_status
            else:
                now = time.ticks_ms()
                diff = time.ticks_diff(now,self.countdown_start_time)
                if diff>=1000:
                    self.countdown_start_time = now
                    self.seconds_left = self.seconds_left-1
                    if self.seconds_left==0:
                        self.counting_down=False
                        self.fire_shutter()
                    else:
                        self.display_status()
            
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
