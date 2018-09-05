# for debug logging
import logging

# substitute array coordinate mappings fer better reading
X, Y = 0, 1
L, T, R, B = 0, 1, 2, 3

log = logging.getLogger('Frame')


class Frame:

    def __init__(self, key=False):
        self.rect = [0, 0, 0, 0]
        self.crop = [0, 0, 0, 0]
        self.alpha = 255
        self.original_size = [0.0, 0.0]
        self.key = key

    def __repr__(self):
        z = [round(x, 1) for x in self.zoom]
        return ("{0.rect} {0.crop} {0.alpha} {1}").format(self, z)

    def str_title():
        return "(   L,   T     R,   B alpha  LCRP,TCRP,RCRP,BCRP  XZOM,YZOM)"

    def __str__(self):
        return ("(%4d,%4d  %4d,%4d  %4d  %4d,%4d,%4d,%4d  %1.2f,%1.2f)" %
                tuple(self.rect + [self.alpha] + self.crop + self.zoom()))

    def __eq__(self, other):
        # do NOT compare zoom
        return self.rect == other.rect and self.crop == other.crop and self.alpha == other.alpha

    def zoom(self):
        """ calculate zoom factors from relation between given size and
            width and height of rect in all channels
        """
        if self.crop != [0, 0, 0, 0]:
            return [(self.rect[R] - self.rect[L]) / self.original_size[X], (self.rect[B] - self.rect[T]) / self.original_size[Y]]
        return [0.0, 0.0]

    def cropped(self):
        if not self.rect:
            return None
        z = self.zoom()
        return [self.rect[L] + self.crop[L] * z[X],
                self.rect[T] + self.crop[T] * z[Y],
                self.rect[R] - self.crop[R] * z[X],
                self.rect[B] - self.crop[B] * z[Y]]

    def corner(self, ix, iy): return [self.rect[ix], self.rect[iy]]

    def width(self): return self.rect[R] - self.rect[L]

    def height(self): return self.rect[B] - self.rect[T]

    def size(self): return self.width(), self.height()

    def invisible(self):
        return (self.rect is None or
                self.rect[R] == self.rect[L] or
                self.rect[T] == self.rect[B] or
                self.alpha == 0)
