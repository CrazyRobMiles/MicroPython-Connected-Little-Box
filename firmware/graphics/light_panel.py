from graphics.colours import BLACK,RED,GREEN,BLUE


class LightPanel:

    # The Neopixel buffer is arranged in GRB sequence which 
    # we need to flip when writing RGB

    def write_grb(self,pos,r, g, b):
        dest=self.buf
        dest[pos]=int(r)
        dest[pos+1]=int(g)
        dest[pos+2]=int(b)

    def write_rgb(self,pos,r, g, b):
        dest=self.buf
        dest[pos]=int(g)
        dest[pos+1]=int(r)
        dest[pos+2]=int(b)

    def __init__(self, map, pixeltype, pixels, brightness=1):
        self.map = map
        self.get_offset = map.get_offset
        self.pixels = pixels
        self.buf = self.pixels.buf
        self.brightness = brightness
        if pixeltype == "GRB":
            print("GRB Pixels")
            self.write_col = self.write_grb
        else:
            self.write_col = self.write_rgb
            print("RGB Pixels")
    
    def clear_col(self, colour=BLACK):
        int_col = (int(colour[0]),int(colour[1]),int(colour[2]))
        self.pixels.fill(int_col)
        return

    def wash_col(self, colour):
        for p in range(0,self.map.pixel_bytes,3):
            if p[0]==0 and p[1]==0 and p[2]==0:
                self.write_col(p,colour[0],colour[1],colour[2])

    def clear_rgb(self,r=0,g=0,b=0):
        for p in range(0,self.map.pixel_bytes,3):
            self.write_col(p,r,g,b )

    def wash_rgb(self,r,g,b):
        for p in range(0,self.map.pixel_bytes,3):
            if p[0]==0 and p[1]==0 and p[2]==0:
                self.write_col(p,r,g,b)

    def display(self):
        brightness = self.brightness
        dest=self.buf
        for p in range(0,self.map.pixel_bytes):
            if brightness==0:
                dest[p]=0
            elif brightness==1:
                pass
            else:
                dest[p]=int(dest[p]*brightness)

    def render_light(self, source_x, source_y, colour, brightness, opacity):
        int_x = int(source_x)
        int_y = int(source_y)
        p = self.get_offset(int_x,int_y)
        dest = self.buf
        opacity = 1-opacity

        for i in range(0,3):
            dest[p+i]=int(min(255,(dest[p+i]*opacity) + (colour[i]*brightness)))
        return

    def show(self):
        self.pixels.write()

    def set_pixel_col(self,x,y,col):
        p = self.get_offset(x,y)
        self.write_col(p,col[0],col[1],col[2])

    def set_pixel_rgb(self, x, y, r, g, b):
        """Set one pixel at position (x,y) to a colour."""
        p = self.get_offset(x, y)
        self.write_col(p,r,g,b)
