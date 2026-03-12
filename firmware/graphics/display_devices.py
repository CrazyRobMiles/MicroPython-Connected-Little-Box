# --------------------------------------------------------------------
# Hardware wrappers
# --------------------------------------------------------------------

version = "1.0.0"

class DisplayItem:

    LEFT = 0
    CENTRE = 1
    RIGHT = 2

    def __init__(self, x, y, display, width, height, alignment):
        self.display = display
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.alignment = alignment
        self.text_width = 0
        self.text_x = 0
        self.old_text = ""
        
    def do_display(self, text):
        """Draw the item only if the text changed (avoids flicker)."""
        if text == self.old_text:
            return False
        return True

class BitmapDisplayItem(DisplayItem):

    def __init__(self, x, y, display, width, height, alignment,
                 foreground=1, background=0, font="bitmap8",size=1):
        super().__init__(x,y,display,width,height,alignment)
        self.foreground = foreground
        self.background = background
        self.font = font
        self.size = size

    def do_display(self, text):

        if not super().do_display(text):
            return

        # wipe old text
        if self.text_width > 0:
            self.display.set_pen(self.background)
            self.display.rectangle(self.text_x, self.y,
                                   self.text_width, self.height)

        # draw new
        self.display.set_pen(self.foreground)
        self.display.set_font(self.font)
        self.text_width = self.display.measure_text(text, scale=self.size)

        if self.alignment == BitmapDisplayItem.CENTRE:
            self.text_x = (self.width - self.text_width) // 2
        elif self.alignment == BitmapDisplayItem.LEFT:
            self.text_x = self.x
        else:  # RIGHT
            self.text_x = self.x + (self.width - self.text_width)

        self.display.text(text, self.text_x, self.y, scale=self.size)

        self.old_text = text
        return True

class CharacterDisplayItem(DisplayItem):
    def __init__(self, x, y, display, width, height):
        self.display = display
        self.x = x
        self.y = y
        self.width = width
        self.height = height

        self.text_width = 0
        self.text_x = 0
        self.old_text = ""

    def do_display(self, text):
        """Draw the item only if the text changed (avoids flicker)."""
        if text == self.old_text:
            return False

        # wipe old text
        if self.text_width > 0:
            self.display.set_pen(self.background)
            self.display.rectangle(self.text_x, self.y,
                                   self.text_width, self.height)

        # draw new
        self.display.set_pen(self.foreground)
        self.display.set_font(self.font)
        self.text_width = self.display.measure_text(text, scale=self.size)

        if self.alignment == BitmapDisplayItem.CENTRE:
            self.text_x = (self.width - self.text_width) // 2
        elif self.alignment == BitmapDisplayItem.LEFT:
            self.text_x = self.x
        else:  # RIGHT
            self.text_x = self.x + (self.width - self.text_width)

        self.display.text(text, self.text_x, self.y, scale=self.size)

        self.old_text = text
        return True

class DisplayDevice:

    def __init__(self,manager,width,height):
        self.manager=manager
        self.width=width
        self.height=height
        self.display.clear()
        
class GFX_LCDDisplay(DisplayDevice):
    def __init__(self,manager):
        import gfx_pack
        self.board = gfx_pack.GfxPack()
        self.display = self.board.display
        x,y=self.display.get_bounds()
        super().__init__(manager,x,y)

    def clear(self):
        self.display.set_pen(0)
        self.display.clear()

    def update(self):
        self.display.update()

    def text(self, text, x, y, scale):
        self.display.set_pen(15)
        self.display.text(text, x, y, scale=scale)
        
    def measure_text(self, text, scale=1):
        return self.display.measure_text(text, scale)
    
    def get_display_item(self,x,y,width,height,alignment,foreground, background, font,size):
        return BitmapDisplayItem(x,y,self.display,width,height,
                                 alignment,foreground,background,font,size)
        
        
class EInkDisplay(DisplayDevice):
    def __init__(self,manager):
        from picographics import PicoGraphics, DISPLAY_INKY_PACK
        from graphics.display_items import BitmapDisplayItem
        self.display = PicoGraphics(DISPLAY_INKY_PACK)
        x,y=self.display.get_bounds()
        super().__init__(manager,x,y)

    def clear(self):
        self.display.set_pen(15)
        self.display.clear()

    def update(self):
        self.display.update()

    def text(self, text, x, y, scale):
        self.display.set_pen(0)
        self.display.text(text, x, y, scale=scale)

    def measure_text(self, text, scale=1):
        return self.display.measure_text(text, scale)

class Ht16k33_14Seg(DisplayDevice):
    def __init__(self,manager):
        from ht16k33.ht16k33segment14 import HT16K33Segment14
        self.display = HT16K33Segment14(manager.i2c, board=HT16K33Segment14.ADAFRUIT_054)
        super().__init__(manager,4,1)

    def clear(self):
        self.display.clear()

    def update(self):
        self.display.draw()

    def text(self, text):
        count=0
        for ch in text:
            self.display.set_character(ch, count)
            count=count+1
        while count<4:
            self.display.set_character(' ', count)
            count=count+1            

    def measure_text(self, text, scale=1):
        return len(text)

    def get_display_item(self,x,y,width,height):
        return CharacterDisplayItem(x,y,self,width,height)
