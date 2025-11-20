from graphics.colours import BLACK
import math

CLOSE_TOLERANCE = 0.0001

class Sprite:
    SPRITE_STOPPED = 0
    SPRITE_BOUNCE = 1
    SPRITE_WRAP = 2
    SPRITE_MOVE = 3

    def __init__(self, frame):
        self.frame = frame
        self.reset()

    def reset(self):
        self.enabled = False
        self.movingState = Sprite.SPRITE_STOPPED
        self.colour = BLACK
        self.moveSteps = 0
        self.colourSteps = 0
        self.brightnessSteps = 0
        self.x = self.y = 0.0
        self.xSpeed = self.ySpeed = 0.0
        self.redStep = self.greenStep = self.blueStep = 0.0
        self.brightness = 1.0
        self.opacity = 1.0
        self.brightnessStep = 0.0
        self.width = self.frame.lightPanel.map.width
        self.height = self.frame.lightPanel.map.height

    def close_to(self, a, b):
        return abs(a - b) <= CLOSE_TOLERANCE

    def coloursEqual(self, a, b):
        return all([
            self.close_to(a.r, b.r),
            self.close_to(a.g, b.g),
            self.close_to(a.b, b.b)
        ])

    def setColour(self, target):
        self.colour = target
        self.targetColour = target
        self.redStep = self.greenStep = self.blueStep = 0
        self.colourSteps = 0

    def fadeToColour(self, target, steps):
        self.targetColour = target.copy()
        self.redStep = (target.r - self.colour.r) / steps
        self.greenStep = (target.g - self.colour.g) / steps
        self.blueStep = (target.b - self.colour.b) / steps
        self.colourSteps = steps

    def fadeToBrightness(self, target, steps):
        self.targetBrightness = target
        self.brightnessStep = (target - self.brightness) / steps
        self.brightnessSteps = steps

    def moveToPosition(self, targetX, targetY, steps, postState):
        self.destX = targetX
        self.destY = targetY
        self.xSpeed = (targetX - self.x) / steps
        self.ySpeed = (targetY - self.y) / steps
        self.stateWhenMoveCompleted = postState
        self.moveSteps = steps
        self.movingState = Sprite.SPRITE_MOVE

    def update(self):
        if not self.enabled:
            return

        if self.brightnessSteps > 0:
            self.brightness += self.brightnessStep
            self.brightnessSteps -= 1
            if self.brightnessSteps == 0:
                self.brightness = self.targetBrightness
                if self.brightness <= 0:
                    self.enabled = False

        if self.colourSteps > 0:
            self.colour.r += self.redStep
            self.colour.g += self.greenStep
            self.colour.b += self.blueStep
            self.colourSteps -= 1
            if self.colourSteps == 0:
                self.colour = self.targetColour.copy()

        self.move()

    def startBounce(self, xSpeed, ySpeed):
        self.xSpeed = xSpeed
        self.ySpeed = ySpeed
        self.movingState = Sprite.SPRITE_BOUNCE

    def startWrap(self, xSpeed, ySpeed):    
        self.xSpeed = xSpeed
        self.ySpeed = ySpeed
        self.movingState = Sprite.SPRITE_WRAP

    def stop(self): 
        self.movingState = Sprite.SPRITE_STOPPED
        self.xSpeed = 0
        self.ySpeed = 0


    def move(self):
        if self.movingState == Sprite.SPRITE_STOPPED:
            return
        elif self.movingState == Sprite.SPRITE_MOVE:
            self.x += self.xSpeed
            self.y += self.ySpeed
            self.moveSteps -= 1
            if self.moveSteps == 0:
                self.x = self.destX
                self.y = self.destY
                self.movingState = self.stateWhenMoveCompleted
        elif self.movingState == Sprite.SPRITE_BOUNCE:
            self.x += self.xSpeed
            self.y += self.ySpeed
            if (self.x < 0):
                self.x = 0
                self.xSpeed = abs(self.xSpeed)
            if (self.y< 0):
                self.y = 0
                self.ySpeed = abs(self.ySpeed)
            if (self.x >= self.width):
                self.x = self.width-1
                self.xSpeed = -abs(self.xSpeed)
            if (self.y >= self.height):
                self.y = self.height-1
                self.ySpeed = -abs(self.ySpeed)
        elif self.movingState == Sprite.SPRITE_WRAP:
            self.x += self.xSpeed
            self.y += self.ySpeed
            if self.x < 0:
                self.x = self.width - 1
            elif self.x >= self.width:
                self.x = 0
            if self.y < 0:
                self.y = self.height - 1
            elif self.y >= self.height:
                self.y = 0

    def setup(self, colour, brightness, opacity, x, y, xSpeed, ySpeed, movingState, enabled):
        self.fadeToColour(colour, 10)
        self.brightness = brightness
        self.opacity = opacity
        self.x = x
        self.y = y
        self.xSpeed = xSpeed
        self.ySpeed = ySpeed
        self.movingState = movingState
        self.enabled = enabled
