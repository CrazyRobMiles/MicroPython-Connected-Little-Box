version = "1.0.0"

class TextManager():

    font_5x3 = (
        (0, 0),         # 32 - 'Space'
        (23,),          # 33 - '!'
        (3, 0, 3),      # 34 - '"'
        (31, 10, 31),   # 35 - '#'
        (22, 31, 13),   # 36 - '$'
        (9, 4, 18),     # 37 - '%'
        (10, 21, 26),   # 38 - '&'
        (3,),           # 39
        (14, 17),       # 40 - '('
        (17, 14),       # 41 - ')'
        (10, 4, 10),    # 42 - '*'
        (4, 14, 4),     # 43 - '+'
        (16, 8),        # 44 - ','
        (4, 4, 4),      # 45 - '-'
        (16,),          # 46 - '.'
        (8, 4, 2),      # 47 - '/'
        (31, 17, 31),   # 48 - '0'
        (0, 31),        # 49 - '1'
        (29, 21, 23),   # 50 - '2'
        (17, 21, 31),   # 51 - '3'
        (7, 4, 31),     # 52 - '4'
        (23, 21, 29),   # 53 - '5'
        (31, 21, 29),   # 54 - '6'
        (1, 1, 31),     # 55 - '7'
        (31, 21, 31),   # 56 - '8'
        (23, 21, 31),   # 57 - '9'
        (10,),          # 58 - ':'
        (16, 10),       # 59 - ';'
        (4, 10, 17),    # 60 - '<'
        (10, 10, 10),   # 61 - '='
        (17, 10, 4),    # 62 - '>'
        (1, 21, 3),     # 63 - '?'
        (14, 21, 22),   # 64 - '@'
        (30, 5, 30),    # 65 - 'A'
        (31, 21, 10),   # 66 - 'B'
        (14, 17, 17),   # 67 - 'C'
        (31, 17, 14),   # 68 - 'D'
        (31, 21, 17),   # 69 - 'E'
        (31, 5, 1),     # 70 - 'F'
        (14, 17, 29),   # 71 - 'G'
        (31, 4, 31),    # 72 - 'H'
        (17, 31, 17),   # 73 - 'I'
        (8, 16, 15),    # 74 - 'J'
        (31, 4, 27),    # 75 - 'K'
        (31, 16, 16),   # 76 - 'L'
        (31, 2, 31),    # 77 - 'M'
        (31, 14, 31),   # 78 - 'N'
        (14, 17, 14),   # 79 - 'O'
        (31, 5, 2),     # 80 - 'P'
        (14, 25, 30),   # 81 - 'Q'
        (31, 5, 26),    # 82 - 'R'
        (18, 21, 9),    # 83 - 'S'
        (1, 31, 1),     # 84 - 'T'
        (15, 16, 15),   # 85 - 'U'
        (7, 24, 7),     # 86 - 'V'
        (15, 28, 15),   # 87 - 'W'
        (27, 4, 27),    # 88 - 'X'
        (3, 28, 3),     # 89 - 'Y'
        (25, 21, 19),   # 90 - 'Z'
        (31, 17),       # 91 - '['
        (2, 4, 8),      # 92 - '\'
        (17, 31),       # 93 - ']'
        (2, 1, 2),      # 94 - '^'
        (16, 16, 16),   # 95 - '_'
        (1, 2),         # 96 - '`'
        (12, 18, 28),   # 97 - 'a'
        (31, 18, 12),   # 98 - 'b'
        (12, 18, 18),   # 99 - 'c'
        (12, 18, 31),   # 100 - 'd'
        (12, 26, 20),   # 101 - 'e'
        (4, 31, 5),     # 102 - 'f'
        (20, 26, 12),   # 103 - 'g'
        (31, 2, 28),    # 104 - 'h'
        (29,),          # 105 - 'i'
        (16, 13),       # 106 - 'j'
        (31, 8, 20),    # 107 - 'k'
        (31,),          # 108 - 'l'
        (30, 6, 30),    # 109 - 'm'
        (30, 2, 28),    # 110 - 'n'
        (12, 18, 12),   # 111 - 'o'
        (30, 10, 4),    # 112 - 'p'
        (4, 10, 30),    # 113 - 'q'
        (30, 4),        # 114 - 'r'
        (20, 30, 10),   # 115 - 's'
        (4, 30, 4),     # 116 - 't'
        (14, 16, 30),   # 117 - 'u'
        (14, 16, 14),   # 118 - 'v'
        (14, 24, 14),   # 119 - 'w'
        (18, 12, 18),   # 120 - 'x'
        (22, 24, 14),   # 121 - 'y'
        (26, 30, 22),   # 122 - 'z'
        (4, 27, 17),    # 123 - '{'
        (27,),          # 124 - '|'
        (17, 27, 4),    # 125 - '}'
        (6, 2, 3),      # 126 - '~'
        (31, 31, 31) # 127 - 'Full Block'
    )

    def __init__(self, lightPanel):
        self.lightPanel = lightPanel
        self.text=""
        self.text_x = 0
        self.text_y = 0
        self.scroll_count = 0

    # draw the text on the display taking into account scrolling

    def get_char_design(self,ch):
        ch_offset = ord(ch) - ord(' ')
        if ch_offset<0 or ch_offset>len(self.font_5x3):
            return None
        return self.font_5x3[ch_offset]
    
    def draw_text(self):

        if self.text == '':
            return

        x = self.text_x
        y = self.text_y

        column = self.text_char_column

        ch_pos = self.text_char_pos

        while ch_pos < len(self.text):

            if x >= self.lightPanel.map.width:
                return

            ch = self.text[ch_pos]

            char_design = self.get_char_design(ch)

            if char_design == None:
                return

            char_design_length = len(char_design)
            
            while column < char_design_length:
                if x >= self.lightPanel.map.width:
                    return
                # display the character raster
                font_column =char_design[column]
                bit = 1
                draw_y = y

                while(bit<32):
                    if draw_y >= self.lightPanel.map.height:
                        break

                    if font_column & bit:
                        self.lightPanel.set_pixel_col(x,draw_y, self.text_colour)

                    # move on to the next bit in the column
                    bit = bit + bit
                    # move onto the next pixel to draw
                    draw_y = draw_y + 1

                column = column + 1
                x = x + 1

            # reached the end of displaying a character - move to the next one
            x = x + 1
            ch_pos = ch_pos + 1
            column = 0

    def start_scroll(self):

        if len(self.text) == 0:
            return

        self.text_char_column = 0
        self.text_step=0
        self.text_char_pos = 0

        ch = self.text[self.text_char_pos]

        self.text_char_design = self.get_char_design(ch)

    def scroll_text(self):

        if self.scroll_count==0:
            return

        # Move on to the next column in the character
        self.text_char_column = self.text_char_column + 1

        # Have we reached the end of the character?
        if self.text_char_column >= len(self.text_char_design):
            # need to move on to the next character in the grid
            self.text_char_pos = self.text_char_pos + 1
            self.text_char_column=0
           
            if self.text_char_pos >= len(self.text):
                # finished displaying the text
                self.scroll_count = self.scroll_count-1
                if self.scroll_count > 0:
                    self.text_char_pos = 0
                    self.start_scroll()

    def update(self):

        if self.scroll_count==0:
            return

        self.text_step = self.text_step + 1

        if self.text_step >= self.text_step_limit:
            self.scroll_text()
            self.text_step = 0

    def start_text_display(self,text='hello world',colour=(10,10,10),steps=5,x=0,y=0,scroll_count=1):
        # print(f"text:{text} x:{x} y:{y} r:{colour[0]} g:{colour[1]} b:{colour[2]}")

        if len(text) == 0:
            return

        # put some spaces on the front so the text scrolls in from the right
        self.text = text
        self.text_colour = colour
        self.text_step_limit = steps
        self.text_x = x
        self.text_y = y
        self.text_step = 0
        self.scroll_count = scroll_count
        self.start_scroll()

    def draw(self):
        self.draw_text()
        

