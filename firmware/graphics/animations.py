from graphics.sprite import Sprite

import random

def anim_wandering_sprites(frame, no_of_sprites=30):

    frame.background_manager.start_transitions(((50,0,0),(0,50,0),(0,0,50),(0,0,0),(50,50,50)),500)

    frame.clear_sprites()

    for i in range (no_of_sprites):
        sprite = Sprite(frame)
        sprite.x = random.randint(0, frame.lightPanel.map.width)
        sprite.y = random.randint(0, frame.lightPanel.map.height)
        sprite.setColour((random.randint(0,255),random.randint(0,255),random.randint(0,255)))
        sprite.brightness = 0.3
        sprite.opacity = 0.1
        sprite.enabled = True
        sprite.startBounce(random.uniform(-0.5,0.5), random.uniform(-0.5,0.5))
        frame.add_sprite(sprite)

def anim_robot_sprites(frame, no_of_sprites=5,colour=(255,0,0)):

    frame.clear_sprites()

    for i in range (no_of_sprites):
        sprite = Sprite(frame)
        sprite.x = random.randint(0, frame.lightPanel.map.width)
        sprite.y = random.randint(0, frame.lightPanel.map.height)
        sprite.setColour(colour)
        sprite.brightness = 0.3
        sprite.opacity = 0.1
        sprite.enabled = True
        sprite.startBounce(random.uniform(-0.1,0.1), random.uniform(-0.1,0.1))
        frame.add_sprite(sprite)

