from collections import OrderedDict
import re
from enum import IntEnum
from random import randint
from copy import deepcopy

from rv.api import NOTECMD, Pattern, PatternClone, Project, m
from lib.interpolator import Mask, NoteInterpolator


class States(IntEnum):
    """Parser states"""
    (SOURCE, PATTERN, NOTE, INTERPOLATE, SEQUENCER, MODULE) = range(6)


class Parser(object):
    """Parse a script"""

    project = Project()
    pattern = module = None
    track = row = 0
    state = States.SOURCE
    interpolator = NoteInterpolator()

    # [x, y/32, x backup, max pat length]
    sequencer_pos = [0, 0, 0, 0]
    mbuffer = None



    def tempo(self, match):
        """set tempo"""

        self.project.initial_bpm = int(match.group(1))
        return self.state



    def name(self, match):
        """song title"""

        self.project.name = match.group(1)
        return self.state



    def csv_list(self, value):
        """csv to list helper"""

        if ',' in value:
            return value.split(',')

        return [value]



    def connect_modules(self, modules):
        """connect current module to a csv list of modules"""

        for name in self.csv_list(modules):
            if name == '&':
                self.module >> self.project.output
                continue

            module = [md for md in self.project.modules if md.name == name]
            if len(module):
                self.module >> module



    def open_module(self, match):
        """open a new module and close the last one if needed"""

        if self.state == States.MODULE:
            self.connect_modules(self.mbuffer)

        self.mbuffer = match.group(1)
        self.module = None

        return States.MODULE



    def module_param(self, match):
        """three states: module creation then param/value reader"""

        if self.module is None:
            self.module = self.project.new_module(getattr(m, match.group(1)), name=self.mbuffer)
            self.module.color = (randint(0, 255), randint(0, 255), randint(0, 255))
            self.mbuffer = None


        elif self.mbuffer is None:
            self.mbuffer = match.group(1)


        else:
            try:
                value = int(match.group(1))
                setattr(self.module, self.mbuffer, value)
                self.mbuffer = None

            except ValueError:
                setattr(self.module, self.mbuffer, match.group(1))
                self.mbuffer = None


        return self.state



    def close_module(self, match):
        """close module and connect using last parameter"""

        self.connect_modules(match.group(1))
        return States.SOURCE



    def close_pattern(self, match):
        """Close sequence"""
        return States.SOURCE


    def get_pattern(self, name):
        """search pattern by name"""

        for pattern in self.project.patterns:
            if pattern.name == name:
                return pattern

        return False



    def get_module(self, name):
        """search module by name"""

        for module in self.project.modules:
            if module.name == name:
                return module

        return False


    def open_pattern(self, match):
        """Create a new pattern"""

        if self.state == States.MODULE:
            self.connect_modules(self.mbuffer)


        self.track = 0
        self.row = 0


        name = match.group(1)
        lines = 32
        if ',' in match.group(1):
            name, lines = match.group(1).split(',')


        pattern = self.get_pattern(name)
        if not pattern:
            pattern = Pattern()
            pattern.name = name
            self.project += pattern


        pattern.lines = int(lines)
        pattern.x = -pattern.lines - 50
        pattern.appearance_flags = 1
        pattern.bg_color = (randint(0, 255), randint(0, 255), randint(0, 255))
        self.pattern = pattern

        return States.PATTERN



    def set_track(self, match):
        """Set track position"""

        self.row = 0
        self.track = int(match.group(1))
        return self.state



    def set_row(self, match):
        """Set row position"""

        self.row = int(match.group(1))
        return self.state


    def note(self, match):
        """Set note values"""

        self.interpolator.flags = 0
        if self.row < self.pattern.lines:

            note = self.pattern.data[self.row][self.track]

            if hasattr(NOTECMD, match.group(1)):
                self.interpolator.flags |= Mask.NOTE
                note.note = NOTECMD[match.group(1)]

            elif match.group(1) == '-':
                note.note = NOTECMD.NOTE_OFF

            if self.module is not None:
                note.module = self.module.index + 1

            if match.lastindex > 1:
                self.interpolator.flags |= Mask.VEL
                note.vel = int(match.group(2), 16) + 1

        return States.NOTE



    def controller(self, match):
        """Set controller values"""

        self.interpolator.flags |= Mask.CTL
        note = self.pattern.data[self.row][self.track]
        note.ctl = int(match.group(1)[0:4], 16)
        note.val = int(match.group(1)[4:], 16)

        return States.NOTE



    def end_note(self, match):
        """Close note, inc row"""

        self.row += 1
        return States.PATTERN



    def set_module(self, match):
        """Set current module"""

        self.module = self.get_module(match.group(1))
        return self.state



    def start_interpolate(self, match):
        """Start a new interpolation"""

        note = self.pattern.data[self.row - 1][self.track]
        self.interpolator.duration = int(match.group(1))
        self.interpolator.func = self.interpolator.types[match.group(2)]

        if self.interpolator.flags & Mask.VEL:
            self.interpolator.vel1 = note.vel

        if self.interpolator.flags & Mask.CTL:
            self.interpolator.val1 = note.val
            self.interpolator.ctl = note.ctl

        return States.INTERPOLATE




    def end_interpolate(self, match):
        """Close and write interpolation"""

        if self.interpolator.flags & Mask.VEL:
            self.interpolator.vel2 = int(match.group(2), 16) + 1

        if self.interpolator.flags & Mask.CTL:
            self.interpolator.val2 = int(match.group(1)[4:], 16)

        for tick in range(1, self.interpolator.duration):
            note = self.pattern.data[self.row][self.track]

            if self.module is not None:
                note.module = self.module.index + 1

            if self.interpolator.flags & Mask.VEL:
                end = self.interpolator.vel2 - self.interpolator.vel1
                note.vel = int(self.interpolator.func(tick, self.interpolator.vel1, end, self.interpolator.duration))

            if self.interpolator.flags & Mask.CTL:
                end = self.interpolator.val2 - self.interpolator.val1
                note.ctl = self.interpolator.ctl
                note.val = int(self.interpolator.func(tick, self.interpolator.val1, end, self.interpolator.duration))

            self.row += 1

        self.interpolator.flags = 0
        return States.PATTERN



    def open_sequencer(self, match):
        """Open sequencer"""
        return States.SEQUENCER



    def transpose(self, pattern, semitones):
        """clone and transpose"""

        clone = Pattern()
        clone.name = pattern.name
        clone._data = deepcopy(pattern.data)
        for i in range(pattern.lines):
            for j in range(pattern.tracks):
                n = clone.data[i][j]
                if n.note in range(1, 121):
                    n.note = max(1, min(n.note + int(semitones), 122))

        return clone



    def seq_pattern(self, match):
        """Set a pattern in sequencer"""

        names = []
        if '-' in match.group(0):
            names = match.group(0).split('-')
        else:
            names = [match.group(0)]

        self.sequencer_pos[0] = self.sequencer_pos[2]
        for name in names:

            semitones = 0
            if '^' in name:
                name, semitones = name.split('^')

            # pattern = [pt for pt in self.project.patterns if hasattr(pt, 'name') and pt.name == name]
            pattern = self.get_pattern(name)
            if pattern:

                if int(semitones) == 0:
                    clone = PatternClone(source=self.project.patterns.index(pattern))

                else:
                    clone = self.transpose(pattern, semitones)

                clone.x = self.sequencer_pos[0]
                clone.y = self.sequencer_pos[1] * 32
                self.project += clone
                self.sequencer_pos[0] += pattern.lines

        self.sequencer_pos[3] = max(self.sequencer_pos[0] - self.sequencer_pos[2], self.sequencer_pos[3])
        self.sequencer_pos[1] += 1
        return self.state



    def seq_next_line(self, match):
        """increase sequencer position"""

        self.sequencer_pos[0] = self.sequencer_pos[2] + self.sequencer_pos[3]
        self.sequencer_pos[2] = self.sequencer_pos[0]
        self.sequencer_pos[1] = self.sequencer_pos[3] = 0
        return self.state



    def collector(self, match):
        """Garbage collector"""
        return self.state



    regexp = {
        'space'              : r'\s',
        'spaces'             : r'\s+',
        'eol'                : r'\n',
        'name'               : r'name\s+(.+)\n',
        'tempo'              : r'tempo\s+(\d+)\n',
        'blk_line'           : r'^\n',
        'track'              : r't(\d+)',
        'row'                : r'r(\d+)',
        'comment'            : r'#.+\n',
        'lexem'              : r'([^\s]+)',
        'open_pattern'       : r'^([^\s]+): ',
        'close_pattern'      : r'\n\n',
        'open_sequencer'     : r'---.*$',
        'open_module'        : r'^:([^\s]+)',
        'close_module'       : r'([^\s]+)\s*\n\s*\n+',
        'controller'         : r':([a-f0-9]{8})',
        'open_interpolation' : r'(\d+)([/\\-]+)',
        'close_interpolation': r'([a-gA-G][0-9]|[.])',
        'note'               : r'([a-gA-G][0-9]|[.]|-)',
        'full_note'          : r'([a-gA-G][0-9]|[.]|-)\'([a-f0-9]{1,2})',
        'module'             : r'([a-z0-9_]{2,})',
        'note_params'        : r'.:([a-f0-9]{8})',
        'space_eol'          : r'\s|\n',
        'params'             : r':([a-f0-9]{8})',
        'seq_pattern'        : r'([\^a-z0-9_-]{2,})',
        'unmatched'          : r'[^\s]+'
    }

    # parser dictionary
    states_source = OrderedDict()
    states_source[regexp['comment']] = collector
    states_source[regexp['tempo']] = tempo
    states_source[regexp['name']] = name
    states_source[regexp['open_sequencer']] = open_sequencer
    states_source[regexp['open_module']] = open_module
    states_source[regexp['open_pattern']] = open_pattern
    states_source[regexp['blk_line']] = collector

    states_module = OrderedDict()
    states_module[regexp['spaces']] = collector
    states_module[regexp['comment']] = collector
    states_module[regexp['open_module']] = open_module
    states_module[regexp['close_module']] = close_module
    states_module[regexp['open_pattern']] = open_pattern
    states_module[regexp['lexem']] = module_param

    states_pattern = OrderedDict()
    states_pattern[regexp['close_pattern']] = close_pattern
    states_pattern[regexp['open_sequencer']] = open_sequencer
    states_pattern[regexp['comment']] = collector
    states_pattern[regexp['space']] = collector
    states_pattern[regexp['track']] = set_track
    states_pattern[regexp['row']] = set_row
    states_pattern[regexp['controller']] = controller
    states_pattern[regexp['open_interpolation']] = start_interpolate
    states_pattern[regexp['full_note']] = note
    states_pattern[regexp['note']] = note
    states_pattern[regexp['open_pattern']] = open_pattern
    states_pattern[regexp['module']] = set_module

    states_interpolate = OrderedDict()
    states_interpolate[regexp['note_params']] = end_interpolate
    states_interpolate[regexp['full_note']] = end_interpolate
    states_interpolate[regexp['close_interpolation']] = end_interpolate
    states_interpolate[regexp['spaces']] = collector

    states_note = OrderedDict()
    states_note[regexp['space_eol']] = end_note
    states_note[regexp['params']] = controller

    states_sequencer = OrderedDict()
    states_sequencer[regexp['comment']] = collector
    states_sequencer[regexp['seq_pattern']] = seq_pattern
    states_sequencer[regexp['eol']] = seq_next_line
    states_sequencer[regexp['spaces']] = collector
    states_sequencer[regexp['unmatched']] = collector

    lexd = {
        States.SOURCE: states_source,
        States.PATTERN: states_pattern,
        States.INTERPOLATE: states_interpolate,
        States.NOTE: states_note,
        States.SEQUENCER: states_sequencer,
        States.MODULE: states_module
    }


    def parse(self, source):
        """Parse source file"""

        original = source
        while len(source) > 0:
            for regexp in self.lexd[self.state]:
                match = re.match(regexp, source, re.M)
                if match:
                    self.state = self.lexd[self.state][regexp](self, match)
                    source = source[match.end(0):]
                    break
            if source == original:
                error = source[0:20] + '...'
                raise SyntaxError(error)

            original = source

        return self.project
