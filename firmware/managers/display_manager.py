# /managers/display_manager.py
from managers.base_manager import CLBManager
from managers.event import Event
from graphics.display_devices import LCDDisplay,EInkDisplay,Ht16k33_14Seg
import sys

# --------------------------------------------------------------------
# CLB Manager
# --------------------------------------------------------------------

class Manager(CLBManager):
    version = "1.0.2"


    def __init__(self, clb):
        super().__init__(clb, defaults={
            "enabled": True,
            "type": "lcd",      # lcd | eink | HT16K33
            "font": "bitmap8",
            "text_scale": 2,
        })

        self.display = None
        self.items = {}        # holds DisplayItem objects for other managers
        self.clock = None

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

        dtype = self.settings["type"]

        try:
            if dtype == "lcd":
                if gfx_pack is None:
                    raise RuntimeError("GFX Pack unavailable")
                self.display = LCDDisplay()

            elif dtype == "eink":
                if PicoGraphics is None:
                    raise RuntimeError("PicoGraphics unavailable")
                self.display = EInkDisplay()

            else:
                raise ValueError("Unknown display type")

            # Create two example DisplayItems that others may use
            w, h = self.display.width, self.display.height
            fg, bg = 0, 15 if dtype == "eink" else (15, 0)[1]

            graphics_obj = self.display.display   # the real PicoGraphics-like object

            self.items["status"] = BitmapDisplayItem(
                0, h - 16,
                graphics_obj,
                fg, bg,
                self.settings["font"],
                self.settings["text_scale"],
                w // 2, 16,
                BitmapDisplayItem.LEFT
            )

            self.items["clock"] = BitmapDisplayItem(
                w // 2, h - 16,
                graphics_obj,
                fg, bg,
                self.settings["font"],
                self.settings["text_scale"],
                w // 2, 16,
                BitmapDisplayItem.RIGHT
            )

            self.state = self.STATE_OK
            self.set_status(8201, f"Display initialised ({dtype})")

        except Exception as e:
            self.state = self.STATE_ERROR
            sys.print_exception(e)
            self.set_status(8202, f"Display init failed: {e}")

    def setup_services(self):
        self.clock = self.get_service_handle("clock")

    # ----------------------------------------------------------------
    # UPDATE LOOP
    # ----------------------------------------------------------------
    def update(self):
        if not self.enabled or not self.display:
            return

        # simple demo: draw clock
        if self.clock:
            h, m, s = self.clock.time()
            txt = f"{h:02d}:{m:02d}:{s:02d}"

            item = self.items.get("clock")
            if item and item.do_display(txt):
                self.display.update()
                self.events["display.updated"].publish(txt)

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
