version = "1.0.0"

class CoordMap:

    PIXEL_TYPE_STRING = "Pixel-string"
    PIXEL_TYPE_PANELS_X = "Multi-panels-x"
    PIXEL_TYPE_PANELS_Y = "Multi-panels-y"
    PIXEL_TYPE_ALTERNATE_LINE_PANEL = "Alternate-line-panel"

    def build_offset_cache(self):
        """Precompute offset for every (x,y) pixel coordinate."""
        cache = []
        get = self.get_offset_method()

        for y in range(self.height):
            row = []
            for x in range(self.width):
                row.append(get(x, y))
            cache.append(row)

        self.offset_cache = cache
        self.get_offset = self._get_offset_from_cache

    def _get_offset_from_cache(self, x, y):
        return self.offset_cache[y][x]

    def get_offset_pixel_string(self,x,y):
        offset = (y * self.panel_width + x)*3
        # print(f"x:{x} y:{y} p:{offset}")
        return offset

    def get_offset_alternate_line(self,y,x):
        offsetx = x * self.panel_height 
        if x & 1 == 0:
            offsety = y
        else:
            offsety = (self.panel_width-1)-y
        return (offsety+offsetx)*3

    def get_offset_multi_panels_x(self,x, y):
        panel_pixels = self.panel_width * self.panel_height
        x_panel_no = x//self.panel_width
        x_offset = x%self.panel_width
        offset = (x_panel_no * panel_pixels) + x_offset
        offset = offset+(y*self.panel_width)
        return offset*3
    
    def get_offset_multi_panels_y(self,x, y):
        panel_row_pixels = (self.panel_width*self.panel_height)*self.x_panels
        top_left = panel_row_pixels*(self.y_panels-1) + self.panel_height-1 
        row_no = y//self.panel_height
        p = top_left - (row_no*panel_row_pixels)
        y = y - (row_no*self.panel_height)
        p=(p+((self.panel_width*x)-y))*3
        return p

    def get_offset_method(self):
        if self.panel_type==self.PIXEL_TYPE_STRING:
            return self.get_offset_pixel_string
        elif self.panel_type==self.PIXEL_TYPE_PANELS_Y:
            return self.get_offset_multi_panels_y
        elif self.panel_type==self.PIXEL_TYPE_PANELS_X:
            return self.get_offset_multi_panels_x
        elif self.panel_type==self.PIXEL_TYPE_ALTERNATE_LINE_PANEL:
            return self.get_offset_alternate_line
        else:
            return self.get_offset_pixel_string
        return None

    def __init__(self, panel_type = PIXEL_TYPE_ALTERNATE_LINE_PANEL,
                 panel_width=8,panel_height=8,x_panels = 3,y_panels = 2):
        print(f"Panel\nType:{panel_type} panel_width:{panel_width} panel_height:{panel_height} x_panels:{x_panels} y_panels:{y_panels}")
        self.panel_type = panel_type
        self.panel_height=panel_height
        self.panel_width=panel_width
        self.x_panels=x_panels
        self.y_panels=y_panels
        self.width=panel_width*x_panels
        self.height=panel_height*y_panels
        self.pixels = self.width*self.height
        self.pixel_bytes = self.pixels*3
        self.build_offset_cache()


