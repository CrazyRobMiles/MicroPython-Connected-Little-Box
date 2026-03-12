from managers.base_manager import CLBManager
import json
import time
import math
import random
import machine
import sys
import os
import gc
from HullOS.task import Task
from HullOS.engine import Engine
from graphics.colours import find_random_colour

class Manager(CLBManager):
    version = "1.0.1"

    SHOW_INACTIVE="inactive"
    SHOW_WORDS="showing words"
    ANIMATE_WORDS="animating words"
    SHOW_TIME= "showing time"
    
    ALARM_BACKGROUND_COLOUR=(10,10,10)
    ALARM_MINUTE_BACKGROUND_COLOUR=(10,10,255)
    ALARM_HOUR_BACKGROUND_COLOUR=(255,10,10)
    ALARM_ENABLED_BACKGROUND_COLOUR=(255,10,10)
    ALARM_OFF_BACKGROUND_COLOUR=(255,255,10)
    ALARM_TEXT_COLOUR=(20,20,20)
    
    MESSAGE_ALARM_ON=2
    MESSAGE_ALARM_OFF=1
    
    def __init__(self,clb):
        super().__init__(clb,defaults={
            "wordsearch_file": "Clock.json",
            "wordsearch_letter_delay_ms":250,
            "wordsearch_word_delay_ms":1000,
            "wordsearch_display_gap_ms":5000,
            "run_on_power_up":True,
            "alarm_enabled": False,
            "alarm_timeout_ms":30000,
            "alarm_sample_interval_ms":1000,
            "key_repeat_delay_ms":500,
            "key_repeat_interval_ms":333,
            "number_of_audio_tracks":10
        })
        self.show_state = self.SHOW_INACTIVE
        self.pixel = None
        self.word_positions = {}
        self.show_time_generator = None
        self.first_run=True
        self.hour_button_pressed=False
        self.min_button_pressed=False
        self.up_button_pressed=False
        self.down_button_pressed=False
        self.alarm_sounding=False
        self.alarm_start_ms=None
        self.alarm_sample_playing=False
        self.alarm_playback_gap=False
        self.alarm_playback_gap_start_ms=None
        self.alarm_day=0
        self.previous_alarm_hour=0
        self.previous_alarm_min=0
        self.time_of_button_press=None
        self.time_of_button_press_repeat=None
        self.button_repeat_event=None
        self.animation_loaded=False

        # --- static word tables ---
        self.number_words = {
             0: (""),
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
            15: ("QUARTER",),
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
        
        self.number_words_to_sixty = {
             0: ("ZERO",),
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
            30: ("THIRTY",),
            31: ("THIRTY","ONE",),
            32: ("THIRTY","TWO",),
            33: ("THIRTY","THREE",),
            34: ("THIRTY","FOUR",),
            35: ("THIRTY","FIVE",),
            36: ("THIRTY","SIX",),
            37: ("THIRTY","SEVEN",),
            38: ("THIRTY","EIGHT",),
            39: ("THIRTY","NINE",),
            40: ("FORTY",),
            41: ("FORTY", "ONE"),
            42: ("FORTY", "TWO"),
            43: ("FORTY", "THREE"),
            44: ("FORTY", "FOUR"),
            45: ("FORTY", "FIVE"),
            46: ("FORTY", "SIX"),
            47: ("FORTY", "SEVEN"),
            48: ("FORTY", "EIGHT"),
            49: ("FORTY", "NINE"),
            50: ("FIFTY",),
            51: ("FIFTY", "ONE"),
            52: ("FIFTY", "TWO"),
            53: ("FIFTY", "THREE"),
            54: ("FIFTY", "FOUR"),
            55: ("FIFTY", "FIVE"),
            56: ("FIFTY", "SIX"),
            57: ("FIFTY", "SEVEN"),
            58: ("FIFTY", "EIGHT"),
            59: ("FIFTY", "NINE")
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
        
        self.brightness_values=(0.05,0.1,0.3,0.7,1.0)
        
    def setup(self, settings):

        super().setup(settings)

        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        self.wordsearch_letter_delay_ms = settings["wordsearch_letter_delay_ms"]
        self.wordsearch_word_delay_ms = settings["wordsearch_word_delay_ms"]
        self.wordsearch_display_gap_ms = settings["wordsearch_display_gap_ms"]
        self.alarm_timeout_ms =  int(self.settings.get("alarm_timeout_ms", 30000))
        self.alarm_sample_interval_ms =  int(self.settings.get("alarm_sample_interval_ms", 1000))
        self.key_repeat_delay_ms = int(self.settings.get("key_repeat_delay_ms", 500))
        self.key_repeat_interval_ms = int(self.settings.get("key_repeat_interval_ms", 500))
        self.number_of_audio_tracks = int(self.settings.get("number_of_audio_tracks", 10))
        self.alarm_settings=ClockSettingsStore()
        self.alarm_settings.load()

        try:
            self.file = settings["wordsearch_file"]

            if self.file in os.listdir("/"):
                with open(self.file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)

                self.words = self.data["words"]
                
                self.clock_words = {}
                for w in self.words:
                    word = w["word"].upper()
                    if not word in self.clock_words:
                        self.clock_words[word]=[w]
                    else:
                        self.clock_words[word].append(w)
                        
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
        self.pixel = self.get_service_handle("pixel")
        if self.pixel:
            print("[Wordsearch] Connected to pixel service")
        else:
            print("[Wordsearch] Pixel service unavailable")  
            
        self.pixel.set_brightness(self.brightness_values[self.alarm_settings.brightness])   

        self.clock = self.get_service_handle("clock")
        if self.clock:
            print("[Wordsearch] Connected to clock service")
        else:
            print("[Wordsearch] Clock service unavailable")    

        self.dfplayer = self.get_service_handle("dfplayer")
        
        if self.dfplayer:
            print("[Wordsearch] Connected to dfplayer service")
        else:
            print("[Wordsearch] dfplayer service unavailable")    

        # Subscribe to clock minute events
        evt = self.clb.get_event("clock.minute")
        if evt:
            evt.subscribe(self.on_minute_tick)
            
        bindings = [
            ("gpio.hour_button_low", self.on_hour_button_pressed),
            ("gpio.hour_button_high", self.on_hour_button_released),
            ("gpio.min_button_low", self.on_min_button_pressed),
            ("gpio.min_button_high", self.on_min_button_released),
            ("gpio.up_button_low", self.on_up_button_pressed),
            ("gpio.down_button_low", self.on_down_button_pressed),
            ("gpio.up_button_high", self.on_up_button_released),
            ("gpio.down_button_high", self.on_down_button_released),
            ("gpio.player_status_low", self.on_player_status_low),
            ("gpio.player_status_high", self.on_player_status_high)
        ]
        for ev_name, handler in bindings:
            evt = self.clb.get_event(ev_name)
            if evt:
                evt.subscribe(handler)
                print(f"[AlarmApp] Subscribed: {ev_name} -> {handler.__name__}")
            else:
                print(f"[AlarmApp] Event not found: {ev_name} (tilt manager enabled?)")

    def update(self):
        self.update_yielding()
        self.update_alarm()
        self.update_button_repeat()
        
    def teardown(self):
        self.set_status(7012, "Wordsearch torn down")

    def get_time_words(self, hour, minute):
        """
        Return a tuple of word names for the given hour (0–23) and minute (0–59).
        Produces natural word-clock phrases (no 'minutes').
        """
        hour = hour % 12
        words = []

        if minute == 0:
            words.append(self.hour_words[hour])
            words.extend(("OCLOCK",))
            return tuple(words)

        if minute <= 30:
            # Past current hour
            if minute == 15:
                words.extend(("QUARTER", "PAST", self.hour_words[hour]))
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
                words.extend(("QUARTER", "TO", self.hour_words[next_hour]))
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
            if key not in self.clock_words:
                print(f"[WordSearch] Word '{key}' not found")
                continue
            found.append(random.choice(self.clock_words[key]))
        return found

    # Optional helper for debugging
    def print_time_phrase(self, hour, minute):
        print(" ".join(self.get_time_words(hour, minute)))
        
    def play_alarm_sample(self):
        print("Playing alarm sample")
        # First two samples are alarm on and alarm off
        self.dfplayer.play(random.randint(3,self.number_of_audio_tracks))
    
    def start_alarm_playback_gap(self):
        print("starting alarm playback gap")
        self.alarm_playback_gap_start_ms = time.ticks_ms()
        self.alarm_playback_gap = True
    
    def update_alarm_audio(self):
        if self.alarm_playback_gap:
            now = time.ticks_ms()
            if time.ticks_diff(now, self.alarm_playback_gap_start_ms)>self.alarm_sample_interval_ms:
                print("Sample interval ended")
                self.play_alarm_sample()
                self.alarm_playback_gap=False
                
    def update_alarm(self):
        
        if not self.alarm_settings.enabled:
            return
        
        hour,minute,second = self.clock.time()
        
        if(hour==self.alarm_settings.hour and minute==self.alarm_settings.minute):
            year,month,day=self.clock.date()
            if self.alarm_day != day:
                self.sound_alarm() 
                self.alarm_day=day
        
        self.update_alarm_audio()
        
    def sound_alarm(self):
        print("Sounding Alarm")
        self.alarm_sounding=True
        self.stop_show_time()
        if not self.animation_loaded:
            self.pixel.animate("wandering")
            self.animation_loaded = True
        else:
            self.pixel.resume()
        self.alarm_sample_playing = True
        self.alarm_playback_gap = False
        self.play_alarm_sample()
        self.alarm_start_ms = time.ticks_ms()
        
    def clear_alarm(self):
        print("Clearing Alarm")
        self.alarm_sounding=False
        self.dfplayer.stop()
        if self.animation_loaded:
            self.pixel.pause()
        self.start_show_time()
        
    def show_alarm_status(self):
        if self.alarm_settings.enabled:
            self.immediate_time_display(self.ALARM_ENABLED_BACKGROUND_COLOUR,self.ALARM_TEXT_COLOUR,self.alarm_settings.hour,self.alarm_settings.minute,0)
        else:
            r,g,b=self.ALARM_OFF_BACKGROUND_COLOUR
            self.pixel.fill(r, g, b)
        
    def toggle_alarm_enabled(self):
        if self.alarm_settings.enabled:
            self.alarm_settings.enabled = False
            self.dfplayer.play(self.MESSAGE_ALARM_OFF)
        else:
            self.alarm_settings.enabled = True
            self.dfplayer.play(self.MESSAGE_ALARM_ON)
        self.show_alarm_status()

    def end_alarm_time_set(self):
        print("saving the alarm")
        
        if self.previous_alarm_min == self.alarm_settings.minute and self.previous_alarm_hour == self.alarm_settings.hour:
            print("Alarm setting not changed")
        else:
            # allow the alarm to sound again after it has been set
            self.alarm_day=0
            
        self.start_show_time() 
        
    def start_alarm_time_set(self):
        self.previous_alarm_min = self.alarm_settings.minute
        self.previous_alarm_hour = self.alarm_settings.hour
        
        self.stop_show_time()
        
    def complete_brightness_update(self):
        self.pixel.set_brightness(self.brightness_values[self.alarm_settings.brightness])
        self.clb.set_setting(f"App_wordsearch_alarmclock.brightness_level={self.alarm_settings.brightness}")
        # restart the display with the new brightness level
        self.stop_show_time()
        self.start_show_time()
         
    def increase_brightness(self):
        self.alarm_settings.brightness =  self.alarm_settings.brightness+1
        if self.alarm_settings.brightness>=len(self.brightness_values):
            self.alarm_settings.brightness=0
        self.complete_brightness_update()
        
    def decrease_brightness(self):
        self.alarm_settings.brightness = self.alarm_settings.brightness-1
        if self.alarm_settings.brightness<0:
            self.alarm_settings.brightness=len(self.brightness_values)-1
        self.complete_brightness_update()

    def on_hour_button_pressed(self, event, data):
        if self.alarm_sounding:
            self.clear_alarm()
            return
           
        self.hour_button_pressed=True
        
        if self.min_button_pressed:
            self.toggle_alarm_enabled()
        else:
            self.start_alarm_time_set()
            self.immediate_number_display(self.ALARM_BACKGROUND_COLOUR,self.ALARM_HOUR_BACKGROUND_COLOUR,self.alarm_settings.hour)

    def on_hour_button_released(self, event, data):
        if not self.hour_button_pressed:
            return
        
        if not self.min_button_pressed:
            self.end_alarm_time_set()

        self.hour_button_pressed=False
        
    def on_min_button_pressed(self, event, data):
        if self.alarm_sounding:
            self.clear_alarm()
            return

        self.min_button_pressed=True
        
        if self.hour_button_pressed:
            self.toggle_alarm_enabled()
        else:
            self.start_alarm_time_set()
            self.immediate_number_display(self.ALARM_BACKGROUND_COLOUR,self.ALARM_MINUTE_BACKGROUND_COLOUR,self.alarm_settings.minute)

    def on_min_button_released(self, event, data):
        
        if not self.min_button_pressed:
            return
        
        if not self.hour_button_pressed:
            self.end_alarm_time_set()
            
        self.min_button_pressed=False

    def on_up_button_pressed(self, event, data):
        if self.alarm_sounding:
            self.clear_alarm()

        self.start_button_repeat(self.do_up_button_pressed)
        
        self.do_up_button_pressed()
        
    def do_up_button_pressed(self):

        if not self.down_button_pressed and not self.hour_button_pressed and not self.min_button_pressed:
            self.increase_brightness()
        
        self.up_button_pressed = True
        
        if self.down_button_pressed:
            self.sound_alarm()
        
        if self.hour_button_pressed and self.min_button_pressed:
            return
        
        if self.hour_button_pressed:
            self.alarm_settings.hour = self.alarm_settings.hour+1
            if self.alarm_settings.hour>23:
                self.alarm_settings.hour=0
            self.immediate_number_display(self.ALARM_BACKGROUND_COLOUR,self.ALARM_HOUR_BACKGROUND_COLOUR,self.alarm_settings.hour)
        elif self.min_button_pressed:
            self.alarm_settings.minute = self.alarm_settings.minute+1
            if self.alarm_settings.minute>59:
                self.alarm_settings.minute=0
            self.immediate_number_display(self.ALARM_BACKGROUND_COLOUR,self.ALARM_MINUTE_BACKGROUND_COLOUR,self.alarm_settings.minute)

    def on_up_button_released(self, event, data):
        self.up_button_pressed = False
        self.clear_button_repeat()

    def on_down_button_pressed(self, event, data):
        
        if self.alarm_sounding:
            self.clear_alarm()
            return
        
        self.start_button_repeat(self.do_down_button_pressed)
        
        self.do_down_button_pressed()
        
    def do_down_button_pressed(self):
        
        if not self.up_button_pressed and not self.hour_button_pressed and not self.min_button_pressed:
            self.decrease_brightness()

        self.down_button_pressed=True

        if self.up_button_pressed:
            self.sound_alarm()
        
        if self.hour_button_pressed and self.min_button_pressed:
            return
        
        if self.hour_button_pressed:
            self.alarm_settings.hour = self.alarm_settings.hour-1
            if self.alarm_settings.hour<0:
                self.alarm_settings.hour=23
            self.immediate_number_display(self.ALARM_BACKGROUND_COLOUR,self.ALARM_HOUR_BACKGROUND_COLOUR,self.alarm_settings.hour)
        elif self.min_button_pressed:
            self.alarm_settings.minute = self.alarm_settings.minute-1
            if self.alarm_settings.minute<0:
                self.alarm_settings.minute=59
            self.immediate_number_display(self.ALARM_BACKGROUND_COLOUR,self.ALARM_MINUTE_BACKGROUND_COLOUR,self.alarm_settings.minute)

    def on_down_button_released(self, event, data):
        self.down_button_pressed=False
        self.clear_button_repeat()
        
    def button_repeat(self):
        self.button_repeat_event()
        
    def start_button_repeat(self,button_event):
        
        if(self.time_of_button_press!= None):
            self.clear_button_repeat()
            
        self.button_repeat_event = button_event
        self.time_of_button_press=time.ticks_ms()
        
    def clear_button_repeat(self):
        self.time_of_button_press=None
        self.time_of_button_press_repeat=None

    def update_button_repeat(self):
        
        if self.time_of_button_press==None:
            return
        
        now = time.ticks_ms()
        
        if self.time_of_button_press_repeat != None:
            if time.ticks_diff(now,self.time_of_button_press_repeat)>self.key_repeat_interval_ms:
                self.button_repeat()
                self.time_of_button_press_repeat = now
            return
                
        if time.ticks_diff(now, self.time_of_button_press)>self.key_repeat_delay_ms:
            self.button_repeat()
            self.time_of_button_press_repeat = now

    def on_player_status_low(self, event, data):
        print("Player low")

    def on_player_status_high(self, event, data):
        print("Sound playback ended")
        now = time.ticks_ms()
        if time.ticks_diff(now, self.alarm_start_ms)>self.alarm_timeout_ms:
            print("clearing alarm")
            self.clear_alarm()
        else:
            if self.alarm_sounding:
                self.start_alarm_playback_gap()

    def on_minute_tick(self, event, data):
        if self.first_run:
            if self.settings["run_on_power_up"]:
                print("Starting wordsearch display")
                self.first_run=False
                self.start_show_time()
        self.alarm_settings.update()

    def get_interface(self):
        return {
            "animate": ("Animate the words in the grid", self.animate_wordsearch),
            "show": ("Show all words in the grid", self.show_wordsearch),
            "time": ("Show the time as words", self.start_show_time),
            "test": ("Test the alarm sounding", self.test_alarm)
        }
        
    def test_alarm(self):
        hour,minute,second = self.clock.time()
        self.alarm_settings.hour=hour
        self.alarm_settings.minute=minute

    def animate_words (self):
        try:
            self.show_state = self.ANIMATE_WORDS
            self.pixel.fill(0, 0, 0)
            self.pixel.show()
            while True:
                x = random.choice(self.words)
                colour = find_random_colour()
                for cell in x["cells"]:
                    row = int(cell["row"])
                    col = int(cell["col"])
                    self.pixel.set_rgb(row, col, colour[0], colour[1], colour[2])
                    self.pixel.show()
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

    def phrase_display(self,phrase,background,foreground):
        back_r,back_g,back_b=background
        fore_r,fore_g,fore_b=foreground
        self.pixel.fill(back_r, back_g, back_b)
        
        for p in phrase:
            cells = p.get("cells", [])
            for cell in cells:
                r = int(cell["row"])
                c = int(cell["col"])
                self.pixel.set_rgb(r, c, fore_r,fore_g, fore_b)
        
        self.pixel.show()

    def immediate_number_display(self,background,foreground,number):

        found = []
        
        words = self.number_words_to_sixty[number]
        
        for w in words:
            key = w.upper()
            if key not in self.clock_words:
                print(f"[WordSearch] Word '{key}' not found")
                continue
            found.append(random.choice(self.clock_words[key]))

        self.phrase_display(found,background,foreground)

    def immediate_time_display(self,background,foreground,hour,minute,sec):

        phrase_words = self.get_word_positions_for_time(hour, minute)

        self.phrase_display(phrase_words,background,foreground)
        
    def show_time(self):
        try:
            self.show_state = self.SHOW_TIME
            while self.show_state == self.SHOW_TIME:
                hour,minute,second = self.clock.time()
                phrase_words = self.get_word_positions_for_time(hour, minute)

                self.pixel.fill(0, 0, 0)
                self.pixel.show()

                for p in phrase_words:
                    colour = find_random_colour()
                    cells = p.get("cells", [])
                    for cell in cells:
                        r = int(cell["row"])
                        c = int(cell["col"])
                        self.pixel.set_rgb(r, c, colour[0], colour[1], colour[2])
                        self.pixel.show()
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
            self.pixel.fill(0, 0, 0)
            self.pixel.show()
            for x in self.words:
                colour = find_random_colour()
                for cell in x["cells"]:
                    row = int(cell["row"])
                    col = int(cell["col"])
                    self.pixel.set_rgb(row, col, colour[0], colour[1], colour[2])
                    self.pixel.show()
                    start = time.ticks_ms()
                    while time.ticks_diff(time.ticks_ms(), start) < self.wordsearch_letter_delay_ms:
                        yield  # pause until next frame
                start = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), start) < self.wordsearch_word_delay_ms:
                    yield
                self.pixel.fill(0, 0, 0)
                self.pixel.show()
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
        
    def stop_show_time(self):
        self.change_state(None)

class ClockSettingsStore:
    __slots__ = (
        "hour", "minute", "brightness",
        "_path",
        "_last_hour", "_last_minute", "_last_brightness"
    )

    def __init__(self, path="/clock_settings.json",
                 hour=7, minute=30, brightness=4,enabled=False):
        self._path = path

        # Current values
        self.hour = int(hour)
        self.minute = int(minute)
        self.brightness = int(brightness)
        self.enabled = bool(enabled)
        

        # Last saved values
        self._last_hour = None
        self._last_minute = None
        self._last_brightness = None
        self._last_enabled = None

    # ------------------------------------------------------------
    # Load from JSON (if present)
    # ------------------------------------------------------------
    def load(self):
        print("Loading alarm settings")
        try:
            try:
                import ujson as json
            except ImportError:
                import json

            with open(self._path, "rb") as f:
                d = json.load(f)

            self.hour = int(d.get("hour", self.hour))
            self.minute = int(d.get("minute", self.minute))
            self.brightness = int(d.get("brightness", self.brightness))
            self.enabled = bool(d.get("enabled", self.enabled))

        except OSError:
            # File missing is fine
            pass

        # Establish baseline
        self._last_hour = self.hour
        self._last_minute = self.minute
        self._last_brightness = self.brightness
        self._last_enabled = self.enabled

    def save(self):
        print("Saving alarm settings")
        gc.collect()
        tmp = self._path + ".tmp"

        # IMPORTANT: open in text mode so ujson can stream to a real file object
        with open(tmp, "w") as f:
            json.dump({
                "hour": self.hour,
                "minute": self.minute,
                "brightness": self.brightness,
                "enabled": self.enabled
            }, f)

        try:
            os.remove(self._path)
        except OSError:
            print("remove failed")
            pass
        os.rename(tmp, self._path)

        self._last_hour = self.hour
        self._last_minute = self.minute
        self._last_brightness = self.brightness
        self._last_enabled = self.enabled
        
        gc.collect()

    # ------------------------------------------------------------
    # Call once per minute
    # ------------------------------------------------------------
    def update(self):
        if (self.hour != self._last_hour or
            self.minute != self._last_minute or
            self.brightness != self._last_brightness or
            self.enabled != self._last_enabled):
            print("   Alarm settings changed - saving")
            self.save()
