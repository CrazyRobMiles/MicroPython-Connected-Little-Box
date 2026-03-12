version = "1.0.0"

from graphics.colours import ColourFadeManager
from graphics.sprite import Sprite
from graphics.light_panel import LightPanel

class Frame:
    def __init__(self, lightPanel):
        self.lightPanel=lightPanel
        self.background_manager = ColourFadeManager()
        self.sprites = []

    def clear(self):
        self.lightPanel.clear_col(self.background_manager.col)

    def add_sprite(self, sprite):
        self.sprites.append(sprite)

    def clear_sprites(self):
        self.sprites = []

    def update(self):
        self.background_manager.update()
        for sprite in self.sprites:
            sprite.update()

    def render(self):
        self.clear()
        for sprite in self.sprites:
            if sprite.enabled:
                self.lightPanel.render_light(sprite.x, sprite.y, sprite.colour, sprite.brightness, sprite.opacity)

    def display(self):
        self.lightPanel.display()

