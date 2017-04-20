from enum import IntEnum

class Mask(IntEnum):
    """Mask values for interpolator"""
    NOTE = 1
    VEL = 2
    CTL = 4


class NoteInterpolator(object):
    """Used to interpolate notes, velocity and controller values"""

    flags = 0
    vel1 = vel2 = 0
    val1 = val2 = 0
    ctl = 0
    duration = 0

    def __init__(self):
        self.types = {
            r'-': self.linear,
            r'/': self.ease_in,
            '\\': self.ease_out,
            '/\\': self.ease_in_out
        }

    def linear(self, tick, start, end, duration):
        """Linear interpolation"""
        return end * tick / duration + start

    def ease_in(self, tick, start, end, duration):
        """Cubic ease-in"""
        tick /= duration
        return end * tick * tick * tick + start

    def ease_out(self, tick, start, end, duration):
        """Cubic ease-out"""
        tick /= duration
        tick -= 1
        return end * (tick * tick * tick + 1) + start

    def ease_in_out(self, tick, start, end, duration):
        """Cubic in/out"""
        tick /= duration / 2
        if tick < 1:
            return end / 2 * tick * tick * tick + start
        tick -= 2
        return end / 2 * (tick * tick * tick + 2) + start

