from managers.base import CLBManager
import json
import time
import math
import random
import machine
import sys
import os
from HullOS.task import Task
from HullOS.engine import Engine
from graphics.colours import find_random_colour

class Manager(CLBManager):
    version = "1.0.0"
    dependencies = ['clock']

    SHOW_INACTIVE="inactive"
    SHOW_WORDS="showing words"
    ANIMATE_WORDS="animating words"
    SHOW_TIME= "showing time"

    def __init__(self,clb):
        super().__init__(clb,defaults={
            "wordsearch_file": "Clock.json",
            "wordsearch_letter_delay_ms":250,
            "wordsearch_word_delay_ms":1000,
            "wordsearch_display_gap_ms":5000,
            "run_on_power_up":True
        })
        self.show_state = self.SHOW_INACTIVE
        self.pixels = None
        self.word_positions = {}
        self.show_time_generator = None

        # --- static word tables ---
        self.number_words = {
             0: (),
             1: ("ONE",),
             2: ("TWO",),
             3: ("THREE",),
             4: ("FOUR",),
             5: ("FIVE",),
             6: ("SIX",),
             7: ("SEVEN",),
             8: ("EIGHT",),
             9: ("NINE",),
            10: ("TEN",),
            11: ("ELEVEN",),
            12: ("TWELVE",),
            13: ("THIRTEEN",),
            14: ("FOURTEEN",),
            15: ("FIFTEEN",),
            16: ("SIXTEEN",),
            17: ("SEVENTEEN",),
            18: ("EIGHTEEN",),
            19: ("NINETEEN",),
            20: ("TWENTY",),
            21: ("TWENTY", "ONE"),
            22: ("TWENTY", "TWO"),
            23: ("TWENTY", "THREE"),
            24: ("TWENTY", "FOUR"),
            25: ("TWENTY", "FIVE"),
            26: ("TWENTY", "SIX"),
            27: ("TWENTY", "SEVEN"),
            28: ("TWENTY", "EIGHT"),
            29: ("TWENTY", "NINE"),
            30: ("HALF",),
        }

        self.hour_words = {
             0: "TWELVE",
             1: "ONE",
             2: "TWO",
             3: "THREE",
             4: "FOUR",
             5: "FIVE",
             6: "SIX",
             7: "SEVEN",
             8: "EIGHT",
             9: "NINE",
            10: "TEN",
            11: "ELEVEN",
            12: "TWELVE",
        }

    def get_time_words(self, hour, minute):
        """
        Return a tuple of word names for the given hour (0–23) and minute (0–59).
        Produces natural word-clock phrases (no 'minutes').
        """
        hour = hour % 12
        words = []

        if minute == 0:
            words.append(self.hour_words[hour])
            words.extend(("OCLOCK"))
            return tuple(words)

        if minute <= 30:
            # Past current hour
            if minute == 15:
                words.extend(("FIFTEEN", "PAST", self.hour_words[hour]))
            elif minute == 30:
                words.extend(("HALF", "PAST", self.hour_words[hour]))
            elif minute == 1:
                words.extend(("ONE", "PAST", self.hour_words[hour]))
            else:
                words.extend(self.number_words[minute])
                words.extend(("PAST", self.hour_words[hour]))
        else:
            # To next hour
            minutes_to = 60 - minute
            next_hour = (hour + 1) % 12
            if minutes_to == 15:
                words.extend(("FIFTEEN", "TO", self.hour_words[next_hour]))
            elif minutes_to == 1:
                words.extend(("ONE", "TO", self.hour_words[next_hour]))
            else:
                words.extend(self.number_words[minutes_to])
                words.extend(("TO", self.hour_words[next_hour]))

        return tuple(words)

    def get_word_positions_for_time(self, hour, minute):
        """
        Return list of placement dicts for all words needed to display this time.
        """
        words = self.get_time_words(hour, minute)

        print(words)

        found = []

        for w in words:
            key = w.upper()
            if key not in self.word_positions:
                print(f"[WordSearch] Word '{key}' not found in Clock.json")
                continue
            found.append(self.word_positions[key])
        return found

    # Optional helper for debugging
    def print_time_phrase(self, hour, minute):
        print(" ".join(self.get_time_words(hour, minute)))

    def setup(self, settings):

        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        self.wordsearch_letter_delay_ms = settings["wordsearch_letter_delay_ms"]
        self.wordsearch_word_delay_ms = settings["wordsearch_word_delay_ms"]
        self.wordsearch_display_gap_ms = settings["wordsearch_display_gap_ms"]

        try:
            self.file = settings["wordsearch_file"]

            if self.file in os.listdir("/"):
                with open(self.file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)

                self.words = self.data["placements"]

                self.word_positions = {w["word"].upper(): w for w in self.words}                

                self.set_status(7001, f"Wordsearch {self.version} started")
                self.state = self.STATE_OK
            else:
                print(f"Wordsearch {self.file} not found.")
                self.status = STATE_ERROR = "error"
                return
        except Exception as e:
            self.state = self.STATE_ERROR
            sys.print_exception(e)
            self.set_status(7002, f"Wordsearch init error: {e}")

    def setup_services(self):
        # Called after interface is built and pixel manager is ready
        self.pixels = self.get_service_handle("pixel")
        if self.pixels:
            print("[Wordsearch] Connected to pixel service")
        else:
            print("[Wordsearch] Pixel service unavailable")        

        self.clock = self.get_service_handle("clock")
        if self.clock:
            print("[Wordsearch] Connected to clock service")
        else:
            print("[Wordsearch] Clock service unavailable")        

        # Subscribe to clock minute events
        evt = self.clb.get_event("clock.minute")
        if evt:
            evt.subscribe(self.on_minute_tick)

    def on_minute_tick(self, event, data):
        print("[Wordsearch] Minute tick:", data)
        # update display etc

    def update(self):
        self.update_yielding()
        
    def teardown(self):
        self.set_status(7012, "Wordsearch torn down")

    def get_interface(self):
        return {
            "animate": ("Animate the words in the grid", self.animate_wordsearch),
            "show": ("Show all words in the grid", self.show_wordsearch),
            "time": ("Show the time as words", self.start_show_time)
        }

    def animate_words (self):
        try:
            self.show_state = self.ANIMATE_WORDS
            self.pixels.fill(0, 0, 0)
            self.pixels.show()
            while True:
                x = random.choice(self.words)
                colour = find_random_colour()
                for cell in x["cells"]:
                    row = int(cell["row"])
                    col = int(cell["col"])
                    self.pixels.set_rgb(row, col, colour[0], colour[1], colour[2])
                    self.pixels.show()
                    start = time.ticks_ms()
                    while time.ticks_diff(time.ticks_ms(), start) < 5:
                        yield  # pause until next frame
                start = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), start) < 20:
                    yield
                if not self.show_state == self.ANIMATE_WORDS:
                    break

        except GeneratorExit:
            print("Been told to stop")
        except Exception as e:
            sys.print_exception(e)
            print(f"Something went wrong in animate_words:{e}")
        finally: 
            print("Show words complete")
            self.show_state = self.SHOW_INACTIVE
        return

    def show_time(self):
        try:
            self.show_state = self.SHOW_TIME
            while self.show_state == self.SHOW_TIME:
                hour,minute,second = self.clock.time()
                phrase_words = self.get_word_positions_for_time(hour, minute)

                self.pixels.fill(0, 0, 0)
                self.pixels.show()

                for p in phrase_words:
                    colour = find_random_colour()
                    cells = p.get("cells", [])
                    for cell in cells:
                        r = int(cell["row"])
                        c = int(cell["col"])
                        self.pixels.set_rgb(r, c, colour[0], colour[1], colour[2])
                        self.pixels.show()
                        last_update = time.ticks_ms()
                        while time.ticks_ms() - last_update < self.wordsearch_letter_delay_ms:
                            yield
                    last_update = time.ticks_ms()
                    while time.ticks_ms() - last_update < self.wordsearch_word_delay_ms:
                        yield
                print("[WordSearch] Time phrase displayed:", " ".join(self.get_time_words(hour, minute)))
                last_update = time.ticks_ms()
                while time.ticks_ms() - last_update < self.wordsearch_display_gap_ms:
                    yield
        except GeneratorExit:
            print("Been told to stop")
        except Exception as e:
            sys.print_exception(e)
            print("Something went wrong")
        finally: 
            print("Show time complete")
            self.show_state = self.SHOW_INACTIVE
        return
    
    def show_all_words(self):
        try:
            self.show_state = self.SHOW_WORDS
            self.pixels.fill(0, 0, 0)
            self.pixels.show()
            for x in self.words:
                colour = find_random_colour()
                for cell in x["cells"]:
                    row = int(cell["row"])
                    col = int(cell["col"])
                    self.pixels.set_rgb(row, col, colour[0], colour[1], colour[2])
                    self.pixels.show()
                    start = time.ticks_ms()
                    while time.ticks_diff(time.ticks_ms(), start) < self.wordsearch_letter_delay_ms:
                        yield  # pause until next frame
                start = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), start) < self.wordsearch_word_delay_ms:
                    yield
                self.pixels.fill(0, 0, 0)
                self.pixels.show()
                if not self.show_state == self.SHOW_WORDS:
                    break

        except GeneratorExit:
            print("Been told to stop")
        except Exception as e:
            sys.print_exception(e)
            print(f"Something went wrong in show_all_words:{e}")
        finally: 
            print("Show words complete")
            self.show_state = self.SHOW_INACTIVE
        return


    def show_wordsearch(self):
        self.change_state(self.show_all_words,self.SHOW_WORDS)

    def start_show_time(self):
        self.change_state(self.show_time,self.SHOW_TIME)

    def animate_wordsearch(self):
        self.change_state(self.animate_words,self.ANIMATE_WORDS)
