version = "1.0.0"

class DisplayItem:
    LEFT = 0
    CENTRE = 1
    RIGHT = 2

    def __init__(self, x, y, display, foreground, background, font,
                 size, width, height, alignment):
        self.display = display
        self.x = x
        self.y = y
        self.foreground = foreground
        self.background = background
        self.font = font
        self.size = size
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

        # wipe old text
        if self.text_width > 0:
            self.display.set_pen(self.background)
            self.display.rectangle(self.text_x, self.y,
                                   self.text_width, self.height)

        # draw new
        self.display.set_pen(self.foreground)
        self.display.set_font(self.font)
        self.text_width = self.display.measure_text(text, scale=self.size)

        if self.alignment == DisplayItem.CENTRE:
            self.text_x = (self.width - self.text_width) // 2
        elif self.alignment == DisplayItem.LEFT:
            self.text_x = self.x
        else:  # RIGHT
            self.text_x = self.x + (self.width - self.text_width)

        self.display.text(text, self.text_x, self.y, scale=self.size)

        self.old_text = text
        return True
