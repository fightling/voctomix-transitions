# for debug logging
import logging
# use Frame
from frame import Frame, X, Y, L, T, R, B
# for cloning objects
import copy
# for parsing configuration items
import re

log = logging.getLogger('Composites')


class Composites:
    """ a namespace for composite related methods
    """

    def configure(cfg, size):
        """ read INI like configuration from <cfg> and return all the defined
            composites. <size> is the overall frame size which all proportional
            (floating point) coordinates are related to.

            Possible attributes:

                attribute                format         default
                NAME.a                 = RECT           no output
                NAME.b                 = RECT           no output
                NAME.crop-a            = CROP           no cropping
                NAME.crop-b            = CROP           no cropping
                NAME.default-a         = INPUT          do not change source
                NAME.default-b         = INPUT          do not change source
                NAME.alpha-a           = ALPHA          opaque
                NAME.alpha-b           = ALPHA          opaque
                NAME.inter             = BOOL           not intermediate

            Value types:

                NAME =  unique composite name
                RECT =  Rectangular coordinates which are given by
                        X/Y WxH
                    or  POS WxH
                    or  X/Y SIZE
                    or  POS SIZE
                    or  *

                        X,Y,W,H can be mixed integer absolute coordinates or
                        float proportions POS and SIZE must both be float
                        proportions.
                        '*' stands for full screen size (0/0 1.0x1.0)

                CROP =  Cropping borders which are given by
                        L/T/R/B
                    or  LR/TB
                    or  LRTB
                    or  *

                        L,T,R,B, LR,TB and LRTB can be mixed integer absolute
                        coordinates or float proportions

                INPUT = Any available input source name (grabber, cam1, cam2,
                        ...)
                ALPHA = numeric value in the range between 0 (invisible) and
                        255 (opaque) or float value between 0.0 (invisible) and
                        1.0 (opaque)
                BOOL =  some value. if non-empty the option will be set ('true'
                        for example)
        """
        # prepare resulting composites dictonary
        composites = dict()
        # walk through composites configuration
        for c_name, c_val in dict(cfg).items():
            if '.' not in c_name:
                raise RuntimeError("syntax error in composite name '{}' "
                                   "(must be: 'name.attribute')"
                                   .format(c_name))
            # split name into name and attribute
            name, attr = c_name.lower().rsplit('.', 1)
            if name not in composites:
                composites[name] = Composite()
            try:
                composites[name].config(attr, c_val, size)
            except RuntimeError as err:
                raise RuntimeError(
                    "syntax error in composite config value at '{}':\n{}"
                    .format(name, err))
        return composites


class Composite:

    def __init__(self, a=Frame(True), b=Frame(True)):
        self.frame = [copy.deepcopy(a), copy.deepcopy(b)]
        self.default = [None, None]
        self.inter = None

    def str_title():
        return "Key A%s\tB%s" % (Frame.str_title(), Frame.str_title())

    def __str__(self):
        return "%s A%s\tB%s" % (" * " if self.A().key else
                                "   ", self.A(), self.A())

    def __eq__(self, other):
        """ compare two composites if they are looking the same
            (e.g. a rectangle with size 0x0=looks the same as one with alpha=0
            and so it is treated as equal here)
        """
        if not (self.A() == other.A() or (self.covered() and other.covered())):
            return False
        elif not (self.B() == other.B() or (self.B().invisible() and other.B().invisible())):
            return False
        return True

    def A(self):
        return self.frame[0]

    def B(self):
        return self.frame[1]

    def swapped(self):
        """ swap A and B source items
        """
        # deep copy everything
        s = copy.deepcopy(self)
        # then swap frames
        s.frame = s.frame[::-1]
        return s

    def config(self, attr, value, size):
        """ set value <value> from INI attribute <attr>.
            <size> is the input channel size
        """
        if attr == 'a':
            self.frame[0].rect = str2rect(value, size)
        elif attr == 'b':
            self.frame[1].rect = str2rect(value, size)
        elif attr == 'crop-a':
            self.frame[0].crop = str2crop(value, size)
        elif attr == 'crop-b':
            self.frame[1].crop = str2crop(value, size)
        elif attr == 'default-a':
            self.default[0] = value
        elif attr == 'default-b':
            self.default[1] = value
        elif attr == 'alpha-a':
            self.frame[0].alpha = str2alpha(value)
        elif attr == 'alpha-b':
            self.frame[1].alpha = str2alpha(value)
        elif attr == 'inter':
            self.inter = value
        # re-calculate zoom factors
        for f in self.frame:
            f.calc_zoom(size)

    def covered(self):
        """ check if below is completely covered by above
            (considers shape with cropping and transparency)
        """
        below, above = self.frame
        if below.invisible():
            return True
        if above.invisible():
            return False
        bc = below.cropped()
        ac = above.cropped()
        # return if above is (semi-)transparent or covers below completely
        return (above.alpha < 255 or
                (bc[L] >= ac[L] and
                 bc[T] >= ac[T] and
                 bc[R] <= ac[R] and
                 bc[B] <= ac[B]))


def absolute(str, max):
    if str == '*':
        assert max
        # return maximum value
        return int(max)
    elif '.' in str:
        assert max
        # return absolute (Pixel) value in proportion to max
        return int(float(str) * max)
    else:
        # return absolute (Pixel) value
        return int(str)


def str2rect(str, size):
    """ read rectangle pair from string '*', 'X/Y WxH', 'X/Y', 'WxH', 'X/Y WH', 'X/Y WH' or 'XY WH'
    """
    # check for '*'
    if str == "*":
        # return overall position and size
        return [0, 0, size[X], size[Y]]

    # check for 'X/Y'
    r = re.match(r'^\s*([.\d]+)\s*/\s*([.\d]+)\s*$', str)
    if r:
        # return X,Y and overall size
        return [absolute(r.group(1), size[X]),
                absolute(r.group(2), size[Y]),
                size[X],
                size[Y]]
    # check for 'WxH'
    r = re.match(r'^\s*([.\d]+)\s*x\s*([.\d]+)\s*$', str)
    if r:
        # return overall pos and W,H
        return [0,
                0,
                absolute(r.group(3), size[X]),
                absolute(r.group(4), size[Y])]
    # check for 'X/Y WxH'
    r = re.match(
        r'^\s*([.\d]+)\s*/\s*([.\d]+)\s+([.\d]+)\s*x\s*([.\d]+)\s*$', str)
    if r:
        # return X,Y,X+W,Y+H
        return [absolute(r.group(1), size[X]),
                absolute(r.group(2), size[Y]),
                absolute(r.group(1), size[X]) + absolute(r.group(3), size[X]),
                absolute(r.group(2), size[Y]) + absolute(r.group(4), size[Y])]
    # check for 'XY WxH'
    r = re.match(r'^\s*(\d+.\d+)\s+([.\d]+)\s*x\s*([.\d]+)\s*$', str)
    if r:
        # return XY,XY,XY+W,XY+H
        return [absolute(r.group(1), size[X]),
                absolute(r.group(1), size[Y]),
                absolute(r.group(1), size[X]) + absolute(r.group(2), size[X]),
                absolute(r.group(1), size[Y]) + absolute(r.group(3), size[Y])]
    # check for 'X/Y WH'
    r = re.match(r'^\s*([.\d]+)\s*/\s*([.\d]+)\s+(\d+.\d+)\s*$', str)
    if r:
        # return X,Y,X+WH,Y+WH
        return [absolute(r.group(1), size[X]),
                absolute(r.group(2), size[Y]),
                absolute(r.group(1), size[X]) + absolute(r.group(3), size[X]),
                absolute(r.group(2), size[Y]) + absolute(r.group(3), size[Y])]
    # check for 'XY WH'
    r = re.match(r'^\s*(\d+.\d+)\s+(\d+.\d+)\s*$', str)
    if r:
        # return XY,XY,XY+WH,XY+WH
        return [absolute(r.group(1), size[X]),
                absolute(r.group(1), size[Y]),
                absolute(r.group(1), size[X]) + absolute(r.group(2), size[X]),
                absolute(r.group(1), size[Y]) + absolute(r.group(2), size[Y])]
    # didn't get it
    raise RuntimeError("syntax error in rectangle value '{}' "
                       "(must be either '*', 'X/Y WxH', 'X/Y', 'WxH', 'X/Y WH', 'X/Y WH' or 'XY WH' where X, Y, W, H may be int or float and XY, WH must be float)".format(str))


def str2crop(str, size):
    """ read crop values pair from string '*' or 'L/T/R/B'
    """
    # check for '*'
    if str == "*":
        # return zero borders
        return [0, 0, 0, 0]
    # check for L/T/R/B
    r = re.match(
        r'^\s*([.\d]+)\s*/\s*([.\d]+)\s*/\s*([.\d]+)\s*/\s*([.\d]+)\s*$', str)
    if r:
        return [absolute(r.group(1), size[X]),
                absolute(r.group(2), size[Y]),
                absolute(r.group(3), size[X]),
                absolute(r.group(4), size[Y])]
    # check for LR/TB
    r = re.match(
        r'^\s*([.\d]+)\s*/\s*([.\d]+)\s*$', str)
    if r:
        return [absolute(r.group(1), size[X]),
                absolute(r.group(2), size[Y]),
                absolute(r.group(1), size[X]),
                absolute(r.group(2), size[Y])]
    # check for LTRB
    r = re.match(
        r'^\s*([.\d]+)\s*$', str)
    if r:
        return [absolute(r.group(1), size[X]),
                absolute(r.group(1), size[Y]),
                absolute(r.group(1), size[X]),
                absolute(r.group(1), size[Y])]
    # didn't get it
    raise RuntimeError("syntax error in crop value '{}' "
                       "(must be either '*', 'L/T/R/B', 'LR/TB', 'LTRB' where L, T, R, B, LR/TB and LTRB must be int or float')".format(str))


def str2alpha(str):
    """ read alpha values from string as float between 0.0 and 1.0 or as int between 0 an 255
    """
    # check for floating point value
    r = re.match(
        r'^\s*([.\d]+)\s*$', str)
    if r:
        # return absolute proportional to 255

        return absolute(r.group(1), 255)
    # didn't get it
    raise RuntimeError("syntax error in alpha value '{}' "
                       "(must be float or int)".format(str))
