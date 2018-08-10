#!/usr/bin/env python3
# for debug logging
import logging
from composites import Composite, Composites
from frame import Frame, L, R, T, B, X, Y
# for calculating square roots
import math
# for generating B-Splines
from scipy import interpolate as spi
# for converting arrays
import numpy as np

V = 2  # distance (velocity) index

log = logging.getLogger('Transitions')


class Transitions:

    def configure(cfg, composites, fps=25):
        """ generate all transitions configured in the INI-like configuration
            string in <cfg> by using the given <composites> and return them
            in a dictonary
        """
        # prepare dictonary
        transitions = dict()
        # walk through all items within the configuration string
        for t_name, t in dict(cfg).items():
            # split animation time and composite sequence from t
            time, sequence = t.split(',')
            time = int(time)
            # calculate frames needed for that animation time
            frames = fps * float(time) / 1000.0
            # prepare list of key frame composites
            keys = []
            try:
                # walk trough composite sequence
                for c_name in [x.strip() for x in sequence.split('/')]:
                    # find a composite with that name
                    keys.append(composites[c_name])
            # log any failed find
            except KeyError as err:
                raise RuntimeError(
                    'composite "{}" could not be found in transition {}'.format(err, name))
            # calculate that transition and place it into the dictonary
            log.debug("calculating transition '%s'" % t_name)
            transitions[t_name] = Transition.calculate(keys, frames - 1)
        # return dictonary
        return transitions

    def travel(composites, previous=None):
        """ return a list of pairs of composites along all possible transitions
            between all given composites by walking the tree of all combinations
        """
        # if there is only one composite
        if len(composites) == 1:
            # transition to itself
            return [composites[0], composites[0]]
        # if call is not from recursion
        if not previous:
            # insert random first station
            return Transitions.travel(composites, composites[0:1])
        # if maximum length has been reached
        if len(previous) == len(composites) * len(composites) + 1:
            # return ready sequence
            return previous
        # for all composites
        for a in composites:
            # check if we haven't had that combination previously
            if not is_in(previous, [previous[-1], a]):
                # try that combination
                r = Transitions.travel(composites, previous + [a])
                # return result if we are ready here
                if r:
                    return r
        # no findings
        return None

    def find(begin, _end, transitions):
        # swap target A/B if requested begin and end is the same
        end = _end.swapped() if begin == _end else _end
        # log caller request
        log.debug("\t    %s\n\t    %s %s" %
                  (begin, end, "(swapped)" if end != _end else ""))
        # try to find a transition with the given start and beginning composite
        result = None
        # search in all known transitions for matching start and end frames
        for t_name, t in transitions.items():
            log.debug("trying transition: %s\n\t    %s\n\t    %s\n\t    %s" %
                      (t_name, Composite.str_title(), t.begin(), t.end()))
            if begin == t.begin() and end == t.end():
                result = t_name, t
                break
        # if nothing was found
        if not result:
            # try searching in reversed transtions
            for t_name, t in transitions.items():
                log.debug("trying transition: %s (reversed)\n\t    %s\n\t    %s\n\t    %s" %
                          (t_name, Composite.str_title(), t.begin(), t.end()))
                if begin == t.end() and end == t.begin():
                    result = t_name + " (reversed)", t.reversed()
                    break
        # still nothing found?
        if not result:
            # log warning
            log.warning("no transition found for:\n\t    %s\n\t    %s" %
                        (begin, end))
            # help yourself!
            return None, None
        # log result
        log.debug("found transition: %s" % result[0])
        return result


class Transition:

    def __init__(self, a, b=None):
        # no overloaded constructors available in python m(
        if b:
            # got lists of frames in a and b with same length?
            assert len(a) == len(b)
            assert type(a[0]) is Frame
            assert type(b[0]) is Frame
            # rearrange composites
            self.composites = [Composite(a[i], b[i]) for i in range(len(a))]
        else:
            # if we got only one list then it must be composites
            assert type(a[0]) is Composite
            self.composites = a

    def __str__(self):
        # remember index when to flip sources A/B
        flip_at = self.flip()
        # add table title
        str = "\tNo. %s\n" % Composite.str_title()
        # add composites until flipping point
        for i in range(flip_at):
            str += ("\t%3d %s A%s\tB%s\n" %
                    (i, " * " if self.A(i).key else "   ", self.A(i), self.B(i)))
        # add composites behind flipping point
        if flip_at < self.frames():
            str += ("\t-----------------------------------------------------------"
                    " FLIP SOURCES "
                    "------------------------------------------------------------\n")
            for i in range(flip_at, self.frames()):
                str += ("\t%3d %s B%s\tA%s\n" %
                        (i, " * " if self.A(i).key else "   ", self.A(i), self.B(i)))
        return str

    def frames(self): return len(self.composites)

    def A(self, n):
        assert type(n) is int
        return self.composites[n].A()

    def B(self, n):
        assert type(n) is int
        return self.composites[n].B()

    def begin(self): return Composite(self.A(0), self.B(0))

    def end(self): return Composite(self.A(-1), self.B(-1))

    def reversed(self): return Transition(self.composites[::-1])

    def append(self, composite):
        assert type(composite) is Composite
        self.composites.append(composite)

    def flip(self):
        """ find the first non overlapping rectangle pair within parameters and
            return it's index
        """
        def overlap(a, b):
            return (a[L] < b[R] and a[R] > b[L] and a[T] < b[B] and a[B] > b[T])

        if self.A(0) == self.B(-1):
            flip = False
            for i in range(self.frames() - 1):
                if not (flip or overlap(self.A(i).cropped(), self.B(i).cropped())):
                    return i
            return self.frames() - 1
        else:
            return self.frames()

    def calculate(composites, frames, a_corner=(R, T), b_corner=(L, T)):
        # extract two lists of frames for use with interpolate()
        a = [c.A() for c in composites]
        b = [c.B() for c in composites]
        # check if begin and end of animation are equal
        if a[-1] == a[0] and b[-1] == b[0]:
            # then swap them
            a[-1], b[-1] = b[-1], a[-1]
        # generate animation
        return Transition(interpolate(a, frames, a_corner),
                          interpolate(b, frames, b_corner))

    def keys(self):
        return [i for i in self.composites if i.A().key]


def frange(x, y, jump):
    """ like range() but for floating point values
    """
    while x < y:
        yield x
        x += jump


def bspline(points):
    """ do a B-Spline interpolation between the given points
        returns interpolated points
    """
    # parameter check
    assert type(points) is np.ndarray
    assert type(points[0]) is np.ndarray and len(points[0]) == 2
    assert type(points[1]) is np.ndarray and len(points[1]) == 2
    # calculation resolution
    resolution = 0.001
    # check if we have more than two points
    if len(points) > 2:
        # do interpolation
        tck, u = spi.splprep(points.transpose(), s=0, k=2)
        unew = np.arange(0, 1.001, resolution)
        return spi.splev(unew, tck)
    elif len(points) == 2:
        # throw points on direct line
        x, y = [], []
        for i in frange(0.0, 1.001, resolution):
            x.append(points[0][X] + (points[1][X] - points[0][X]) * i)
            y.append(points[0][Y] + (points[1][Y] - points[0][Y]) * i)
        return [np.array(x), np.array(y)]
    else:
        return None


def find_nearest(spline, points):
    """ find indices in spline which are most near to the coordinates in points
    """
    nearest = []
    for p in points:
        # calculation lamba fn
        distance = (spline[X] - p[X])**2 + (spline[Y] - p[Y])**2
        # get index of point with the minimum distance
        idx = np.where(distance == distance.min())
        nearest.append(idx[0][0])
    # return nearest points
    return nearest


def measure(points):
    """ measure distances between every given 2D point and the first point
    """
    positions = [(0, 0, 0)]
    # enumerate between all points
    for i in range(1, len(points)):
        # calculate X/Y distances
        dx = points[i][X] - points[i - 1][X]
        dy = points[i][Y] - points[i - 1][Y]
        # calculate movement speed V
        dv = math.sqrt(dx**2 + dy**2)
        # sum up to last position
        dx = positions[-1][X] + abs(dx)
        dy = positions[-1][Y] + abs(dy)
        dv = positions[-1][V] + dv
        # append to result
        positions.append((dx, dy, dv))
    # return array of distances
    return positions


def smooth(x):
    """ smooth value x by using a cosinus wave (0.0 <= x <= 1.0)
    """
    return (-math.cos(math.pi * x) + 1) / 2


def distribute(points, positions, begin, end, x0, x1, n):
    """ from the sub set given by <points>, <begin> and <end> takes <n> points
        whose distances are smoothly distributed
    """
    # calculate overall distance from begin to end
    length = positions[end - 1][V] - positions[begin][V]
    # begin result with the first point
    result = []
    # check if there is no movement
    if length == 0.0:
        for i in range(0, n):
            result.append(points[begin])
    else:
        # calculate start points
        pos0 = smooth(x0)
        pos1 = smooth(x1)
        for i in range(0, n):
            # calculate current x
            x = smooth(x0 + ((x1 - x0) / n) * i)
            # calculate distance on curve from y0 to y
            pos = (x - pos0) / (pos1 - pos0) * length + positions[begin][V]
            # find point with that distance
            for j in range(begin, end):
                if positions[j][V] >= pos:
                    # append point to result
                    result.append(points[j])
                    break
    # return result distribution
    return result


def fade(begin, end, factor):
    """ return value within begin and end at <factor> (0.0..1.0)
    """
    # check if we got a bunch of values to morph
    if type(begin) in [list, tuple]:
        result = []
        # call fade() for every of these values
        for i in range(len(begin)):
            result.append(fade(begin[i], end[i], factor))
    elif type(begin) is int:
        # round result to int if begin is an int
        result = int(round(begin + (end - begin) * factor))
    else:
        # return the resulting float
        result = begin + (end - begin) * factor
    return result


def morph(begin, end, pt, corner, factor):
    result = Frame()
    # calculate current size
    size = fade(begin.size(), end.size(), factor)
    # calculate current rectangle
    result.rect = [pt[X] if corner[X] is L else pt[X] - size[X],
                   pt[Y] if corner[Y] is T else pt[Y] - size[Y],
                   pt[X] if corner[X] is R else pt[X] + size[X],
                   pt[Y] if corner[Y] is B else pt[Y] + size[Y],
                   ]
    # calculate current alpha value and cropping
    result.alpha = fade(begin.alpha, end.alpha, factor)
    result.crop = fade(begin.crop, end.crop, factor)
    # try to find the original size by any rectangle
    s = (begin.original_size(), end.original_size())
    # recalculate zoom
    result.calc_zoom(s[0] if s[0] else s[1])
    return result


def interpolate(key_frames, num_frames, corner):
    """ interpolate <num_frames> points of one corner defined by <corner>
        between the rectangles given by <key_frames>
    """
    # get corner points defined by index_x,index_y from rectangles
    corners = np.array([i.corner(corner[X], corner[Y]) for i in key_frames])
    # interpolate between corners and get the spline points and the indexes of
    # those which are the nearest to the corner points
    spline = bspline(corners)
    # skip if we got no interpolation
    if not spline:
        return [], []
    # find indices of the corner's nearest points within the spline
    corner_indices = find_nearest(spline, corners)
    # transpose point array
    spline = np.transpose(spline)
    # calulcate number of frames between every corner
    num_frames_per_move = int(round(num_frames / (len(corner_indices) - 1)))
    # measure the spline
    positions = measure(spline)
    # fill with point animation from corner to corner
    animation = []
    for i in range(1, len(corner_indices)):
        # substitute indices of corner pair
        begin = corner_indices[i - 1]
        end = corner_indices[i]
        # calculate range of X between 0.0 and 1.0 for these corners
        _x0 = (i - 1) / (len(corner_indices) - 1)
        _x1 = i / (len(corner_indices) - 1)
        # create distribution of points between these corners
        corner_animation = distribute(
            spline, positions, begin, end, _x0, _x1, num_frames_per_move - 1)
        # append first rectangle from parameters
        animation.append(key_frames[i - 1])
        # cound index
        for j in range(len(corner_animation)):
            # calculate current sinus wave acceleration
            frame = morph(key_frames[i - 1], key_frames[i],
                          corner_animation[j], corner,
                          smooth(j / len(corner_animation)))
            # append to resulting animation
            animation.append(frame)
            # next animation step
    # append last rectangle from parameters
    animation.append(key_frames[-1])
    # return rectangle animation
    return animation


def is_in(sequence, part):
    assert len(part) == 2
    for i in range(0, len(sequence) - 1):
        if sequence[i: i + 2] == part:
            return True
    return False
