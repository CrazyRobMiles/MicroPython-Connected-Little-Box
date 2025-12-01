from managers.base import CLBManager
import time
import math
import random
import machine
import sys
import os
from HullOS.task import Task
from HullOS.engine import Engine

class Manager(CLBManager):
    version = "1.0.0"
    dependencies = ["wifi","clock","mqtt"]

    def __init__(self,clb):
        super().__init__(clb,defaults={
            "default_program": "default.pyish",
            "program_folder":"/HullOS/code",
            "run on power up":True
        })
        self.engine = Engine(clb)
        self.first_run = True

    def setup(self, settings):
        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

    def setup_services(self):
        # Called after all managers have been setup
        self.pixels = self.get_service_handle("pixel")
        if self.pixels:
            print("[HullOS] Connected to pixel service")
        else:
            print("[HullOS] Pixel service unavailable")        

        self.clock = self.get_service_handle("clock")
        if self.clock:
            print("[HullOS] Connected to clock service")
        else:
            print("[HullOS] Clock service unavailable")        

    def update(self):
        
		# If a dependency stops, we stop

        if self.unresolved_dependencies():
            if self.state != self.STATE_WAITING:
                self.state = self.STATE_WAITING
                self.set_status(5002, "Hullos paused (waiting for dependencies)")
            return

        if self.state != self.STATE_OK:
            self.state = self.STATE_OK
            self.set_status(5002, "Hullos OK")
            if self.first_run:
                self.first_run = False
                run = self.settings["run on power up"] 
                if run:
                    file = self.settings["default_program"]
                    self.command_start_task("boot",file)

        self.engine.update()

    def teardown(self):
        self.set_status(5012, "HullOS manager torn down")

    def get_interface(self):
        return {
            "start": ("start <name> <file>", self.command_start_task)
        }

    def command_start_task(self,task_name="main",program_name=""):

        if program_name == "":
            print("No program name supplied")
            program_name = self.settings["default_program"]
            print(f"Using:{program_name}")

        print(f"Starting program:{program_name}")

        folder = self.settings["program_folder"]
        print(f"Scanning:{folder}")
        
        try:
            os.stat(folder)        # check exists
        except OSError:
            print(f"Creating program folder:{folder}")
            os.mkdir(folder)       # create folder

        if program_name in os.listdir(folder):
            pass
        else:
            print(f"Program {program_name} not found in {folder}")
            return

        try:
            with open(folder+'/'+program_name, "r") as f:
                code = f.read()
        except Exception as e:
            print(f"Program {program_name} in {folder} read failed")
            sys.print_exception(e)
            return
        
        self.engine.start_task(task_name, code)

        print("Task started")
            


