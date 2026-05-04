from managers.base_manager import CLBDeviceManager
import time
import machine
import neopixel
import sys


class Manager(CLBDeviceManager):
    version = "1.0.0"

    device_default_settings = {
        "pixelpin": 18,
        "count": 8,
        "pixeltype": "RGB",
        "brightness": 1.0,
        "fade_steps": 20,
    }

    def __init__(self, clb):
        super().__init__(clb)
        self.pixels = None
        self.count = 0
        self.brightness = 1.0
        self.fade_steps = 20
        self._current = []    # (r,g,b) at current displayed position (pre-brightness)
        self._target = []     # (r,g,b) fade destination
        self._fade_left = []  # steps remaining in active fade (0 = at target)
        self._seq = []        # list-of-(r,g,b) or None
        self._seq_idx = []    # current position in sequence
        self._seq_rate = []   # ticks to hold at each colour after fade completes
        self._seq_tick = []   # countdown until next colour advance
        self.last_update = time.ticks_ms()

    def setup(self, settings):
        super().setup(settings)
        if not self.enabled:
            self.state = self.STATE_DISABLED
            return

        try:
            pin = machine.Pin(int(settings["pixelpin"]), machine.Pin.OUT)
            self.count = int(settings["count"])
            self.pixeltype = settings["pixeltype"].upper()
            self.brightness = float(settings.get("brightness", 1.0))
            self.fade_steps = int(settings.get("fade_steps", 20))

            self.pixels = neopixel.NeoPixel(pin, self.count)

            self._current   = [(0, 0, 0)] * self.count
            self._target    = [(0, 0, 0)] * self.count
            self._fade_left = [0] * self.count
            self._seq       = [None] * self.count
            self._seq_idx   = [0] * self.count
            self._seq_rate  = [10] * self.count
            self._seq_tick  = [0] * self.count

            for i in range(self.count):
                self._write_hw(i, 0, 0, 0)
            self.pixels.write()

            self.state = self.STATE_OK
            self.set_status(5001, f"Indicator started with {self.count} pixels")

        except Exception as e:
            self.state = self.STATE_ERROR
            sys.print_exception(e)
            self.set_status(5002, f"Indicator init error: {e}")

    # -------------------------------------------------------------------------

    def _write_hw(self, index, r, g, b):
        bf = max(0.0, min(1.0, self.brightness))
        sr, sg, sb = int(r * bf), int(g * bf), int(b * bf)
        if self.pixeltype == "GRB":
            self.pixels[index] = (sg, sr, sb)
        else:
            self.pixels[index] = (sr, sg, sb)

    def _lerp(self, current, target, steps):
        """Advance current one step toward target with steps remaining."""
        if steps <= 1:
            return target
        delta = target - current
        if delta == 0:
            return current
        move = delta // steps
        if move == 0:
            move = 1 if delta > 0 else -1
        return current + move

    # -------------------------------------------------------------------------

    def update(self):
        if not self.enabled or self.pixels is None:
            return

        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_update) < 33:
            return
        self.last_update = now

        dirty = False

        for i in range(self.count):

            if self._seq[i] is not None:
                if self._fade_left[i] == 0:
                    # Arrived at target colour — count down dwell time
                    if self._seq_tick[i] > 0:
                        self._seq_tick[i] -= 1
                    else:
                        # Dwell complete: advance to next colour and start fade
                        self._seq_idx[i] = (self._seq_idx[i] + 1) % len(self._seq[i])
                        self._target[i] = self._seq[i][self._seq_idx[i]]
                        self._fade_left[i] = self.fade_steps
                        self._seq_tick[i] = self._seq_rate[i]

            if self._fade_left[i] > 0:
                cr, cg, cb = self._current[i]
                tr, tg, tb = self._target[i]
                steps = self._fade_left[i]
                nr = self._lerp(cr, tr, steps)
                ng = self._lerp(cg, tg, steps)
                nb = self._lerp(cb, tb, steps)
                self._current[i] = (nr, ng, nb)
                self._fade_left[i] -= 1
                self._write_hw(i, nr, ng, nb)
                dirty = True

        if dirty:
            self.pixels.write()

    # -------------------------------------------------------------------------

    def teardown(self):
        if self.pixels:
            for i in range(self.count):
                self._write_hw(i, 0, 0, 0)
            self.pixels.write()
            self.pixels = None
            self.set_status(5012, "Indicator manager torn down")

    # -------------------------------------------------------------------------

    def get_interface(self):
        return {
            "set":          ("Set pixel immediately: set(index, r, g, b)", self.cmd_set),
            "fade":         ("Fade pixel to colour: fade(index, r, g, b)", self.cmd_fade),
            "fill":         ("Set all pixels immediately: fill(r, g, b)", self.cmd_fill),
            "fade_all":     ("Fade all pixels to colour: fade_all(r, g, b)", self.cmd_fade_all),
            "sequence":     ("Cycle pixel through colours: sequence(index, [[r,g,b],...], rate=10)", self.cmd_sequence),
            "sequence_all": ("Cycle all pixels through colours: sequence_all([[r,g,b],...], rate=10)", self.cmd_sequence_all),
            "stop":         ("Stop sequence on one pixel: stop(index)", self.cmd_stop),
            "stop_all":     ("Stop all sequences", self.cmd_stop_all),
            "off":          ("Turn all pixels off", self.cmd_off),
            "brightness":   ("Set brightness 0.0-1.0: brightness(b)", self.cmd_brightness),
            "test":         ("Show rainbow test pattern", self.cmd_test),
        }

    # -------------------------------------------------------------------------

    def _check_index(self, index):
        return 0 <= index < self.count

    def cmd_set(self, index, r, g, b):
        if not self._check_index(index):
            return f"Index {index} out of range (0-{self.count-1})"
        self._seq[index] = None
        self._current[index] = (r, g, b)
        self._target[index] = (r, g, b)
        self._fade_left[index] = 0
        self._write_hw(index, r, g, b)
        self.pixels.write()

    def cmd_fade(self, index, r, g, b):
        if not self._check_index(index):
            return f"Index {index} out of range (0-{self.count-1})"
        self._seq[index] = None
        self._target[index] = (r, g, b)
        self._fade_left[index] = self.fade_steps

    def cmd_fill(self, r, g, b):
        for i in range(self.count):
            self._seq[i] = None
            self._current[i] = (r, g, b)
            self._target[i] = (r, g, b)
            self._fade_left[i] = 0
            self._write_hw(i, r, g, b)
        self.pixels.write()

    def cmd_fade_all(self, r, g, b):
        for i in range(self.count):
            self._seq[i] = None
            self._target[i] = (r, g, b)
            self._fade_left[i] = self.fade_steps

    def cmd_sequence(self, index, colors, rate=10):
        if not self._check_index(index):
            return f"Index {index} out of range (0-{self.count-1})"
        if not colors or len(colors) < 2:
            return "Sequence needs at least 2 colours"
        self._seq[index] = [tuple(c) for c in colors]
        self._seq_idx[index] = 0
        self._seq_rate[index] = max(1, int(rate))
        self._seq_tick[index] = max(1, int(rate))
        # Fade to first colour immediately
        self._target[index] = self._seq[index][0]
        self._fade_left[index] = self.fade_steps

    def cmd_sequence_all(self, colors, rate=10):
        if not colors or len(colors) < 2:
            return "Sequence needs at least 2 colours"
        for i in range(self.count):
            self.cmd_sequence(i, colors, rate)

    def cmd_stop(self, index):
        if not self._check_index(index):
            return f"Index {index} out of range (0-{self.count-1})"
        self._seq[index] = None
        self.set_status(5004, f"Sequence stopped on pixel {index}")

    def cmd_stop_all(self):
        for i in range(self.count):
            self._seq[i] = None
        self.set_status(5004, "All sequences stopped")

    def cmd_off(self):
        for i in range(self.count):
            self._seq[i] = None
            self._current[i] = (0, 0, 0)
            self._target[i] = (0, 0, 0)
            self._fade_left[i] = 0
            self._write_hw(i, 0, 0, 0)
        self.pixels.write()

    def cmd_brightness(self, brightness):
        self.brightness = max(0.0, min(1.0, float(brightness)))
        for i in range(self.count):
            r, g, b = self._current[i]
            self._write_hw(i, r, g, b)
        self.pixels.write()

    def cmd_test(self):
        colors = [(255,0,0),(255,165,0),(255,255,0),(0,255,0),(0,0,255),(75,0,130),(148,0,211)]
        for i in range(self.count):
            r, g, b = colors[i % len(colors)]
            self._seq[i] = None
            self._current[i] = (r, g, b)
            self._target[i] = (r, g, b)
            self._fade_left[i] = 0
            self._write_hw(i, r, g, b)
        self.pixels.write()
        return f"Test: {self.count} pixels lit"
