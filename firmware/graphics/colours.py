import random

RED=0
GREEN=1
BLUE=2

BLACK=(0,0,0)

colour_char_lookup = {
    'K': BLACK,
    'R': (255, 0, 0),
    'G': (0, 255, 0),
    'B': (0, 0, 255),
    'Y': (255, 255, 0),
    'O': (255, 165, 0),
    'M': (255, 0, 255),
    'C': (0, 255, 255),
    'W': (255, 255, 255),
    'A': (0, 138, 216),
    'V': (143, 0, 255),
    'P': (128, 0, 128),
    'T': (0, 128, 128)
}

# Named colours (subset for brevity)
colour_name_lookup = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "orange": (255, 165, 0),
    "magenta": (255, 0, 255),
    "cyan": (0, 255, 255),
    "white": (255, 255, 255),
    "azure": (0, 138, 216),
    "blueviolet": (138, 43, 226),
    "brown": (165, 42, 42),
    "chartreuse": (127, 255, 0),
    "darkgreen": (0, 100, 0),
    "darkmagenta": (139, 0, 139),
    "darkorange": (255, 140, 0),
    "darkred": (139, 0, 0),
    "darkturquoise": (0, 206, 209),
    "darkviolet": (148, 0, 211),
    "deeppink": (255, 20, 147),
    "deepskyblue": (0, 191, 255),
    "firebrick": (178, 34, 34),
    "forestgreen": (34, 139, 34),
    "gold": (255, 215, 0),
    "indianred": (205, 92, 92),
    "lawngreen": (124, 252, 0),
    "lightseagreen": (32, 178, 170),
    "limegreen": (50, 205, 50),
    "maroon": (128, 0, 0),
    "mediumblue": (0, 0, 205),
    "mediumspringgreen": (0, 250, 154),
    "mediumviolet": (199, 21, 133),
    "midnightblue": (25, 25, 112),
    "navy": (0, 0, 128),
    "orchid": (218, 112, 214),
    "purple": (128, 0, 128),
    "saddlebrown": (139, 69, 19),
    "salmon": (250, 128, 114),
    "seagreen": (46, 139, 87),
    "springgreen": (0, 1, 127),
    "teal": (0, 128, 128),
    "tomato": (255, 99, 71),
    "violet": (143, 0, 1)
}

# Lookups
def find_colour_by_name(name):

    if name == "black":
        return (0, 0, 0)

    return colour_name_lookup.get(name.lower(), None)

def find_colour_by_char(ch):
    return colour_char_lookup.get(ch.upper(), None)

def find_random_colour():
    return random.choice(list(colour_name_lookup.values()))

class ColourFadeManager():
    def __init__(self):
        self.col = [0,0,0]
        self.set_col(BLACK)
        self.deltas = [0,0,0]
        self.colours=None

    def stop_update(self):
        self.current_step=0
        self.no_of_steps=0
        self.colours=[]
        self.colour_number=0

    def set_col(self,new_col):
        self.stop_update()
        for i in range(0,3):
            self.col[i]=new_col[i]

    def update(self):

        if self.no_of_steps==0:
            return

        if self.current_step < self.no_of_steps:
            for i in range(0,3):
                c = self.col[i] + self.deltas[i]
                if c<0:
                    c=0
                if c>255:
                    c=255
                self.col[i]=c
            self.current_step = self.current_step + 1
            return self.col
        else:
            if self.colours==None:
                return
            self.colour_number=self.colour_number+1
            if self.colour_number>= len(self.colours):
                self.colour_number=0
            self.start_fade(self.colours[self.colour_number], self.no_of_steps)

    def start_fade(self,target_col,no_of_steps):
        self.current_step = 0
        self.no_of_steps = no_of_steps
        if no_of_steps == 0:
            self.set_col(target_col)
        else:
            for i in range(0,3):
                self.deltas[i] = (target_col[i] - self.col[i]) / no_of_steps

    def start_transitions(self,colours,no_of_steps):
        self.colours=colours
        self.no_of_steps=no_of_steps
        self.colour_number=0
        self.start_fade(colours[0],no_of_steps)
