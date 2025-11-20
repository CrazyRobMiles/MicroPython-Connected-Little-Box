from graphics.colours import Colour, BLACK

class Led:
    def __init__(self):
        self.colour = BLACK.copy()

    def add_colour_values(self, r, g, b, opacity):
        self.colour.r += r * opacity
        self.colour.g += g * opacity
        self.colour.b += b * opacity
        # Optional: clamp values
        self.colour.r = min(255, self.colour.r)
        self.colour.g = min(255, self.colour.g)
        self.colour.b = min(255, self.colour.b)

class Leds:
    def __init__(self, width, height, show_fn, set_pixel_fn):
        self.width = width
        self.height = height
        self.norm_width = 1.0
        self.norm_height = height / width
        self.show = show_fn
        self.set_pixel = set_pixel_fn
        self.leds = [[Led() for _ in range(height)] for _ in range(width)]

    def clear(self, colour=BLACK):
        for y in range(self.height):
            for x in range(self.width):
                self.leds[x][y].colour = colour.copy()

    def wash(self, colour):
        for y in range(self.height):
            for x in range(self.width):
                c = self.leds[x][y].colour
                if c.r == 0 and c.g == 0 and c.b == 0:
                    self.leds[x][y].colour = colour.copy()

    def xy_to_index(self,x, y):
        # Assumes panels are laid out left-to-right
        panel_index = x // 8
        local_x = x % 8
        index = panel_index * 64 + (y * 8) + local_x
        return index
    
    def display(self, brightness=1.0):
        i = 0
        for y in range(self.height):
            for x in range(self.width):
                c = self.leds[x][y].colour
                pos = self.xy_to_index(x, y)
                self.set_pixel(pos, c.r * brightness, c.g * brightness, c.b * brightness)
                i += 1
        self.show()

    def dump(self):
        print(f"Leds width: {self.width} height: {self.height}")
        for y in range(self.height):
            for x in range(self.width):
                c = self.leds[x][y].colour
                print(f"  r:{c.r:.2f} g:{c.g:.2f} b:{c.b:.2f}")

    def render_light(self, source_x, source_y, colour, brightness, opacity):
        int_x = int(source_x)
        int_y = int(source_y)

        for dx in [-1, 0, 1]:
            px = (int_x + dx) % self.width
            for dy in [-1, 0, 1]:
                py = (int_y + dy) % self.height
                dx2 = source_x - (px + 0.5)
                dy2 = source_y - (py + 0.5)
                dist2 = dx2 * dx2 + dy2 * dy2
                if dist2 < 1:
                    factor = 1 - dist2
                    r = colour.r * brightness * factor
                    g = colour.g * brightness * factor
                    b = colour.b * brightness * factor
                    self.leds[px][py].add_colour_values(r, g, b, opacity)
