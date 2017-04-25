import re

class Resolver(object):

    def stretch(self, match):
        """stretch sequence (buggy for now - nb of notes must be a multiple of stretch factor)"""

        dest = int(match.group(2)[1:])
        seq = re.sub(' +', ' ', match.group(3)).strip(' ').split(' ')
        src = len(seq)
        scale = src / dest
        buf = ''
        for i in range(0, dest):
            position = i * scale
            if position.is_integer():
                buf += seq[int(position)] + ' '
            else:
                buf += '. '
        return buf



    def repeat(self, match):
        """Repeat x times a string, used by re.sub() to resolve x(expr)"""

        if 's' in match.group(2):
            return self.stretch(match)

        try:
            rep = match.group(1) + (match.group(3) + ' ') * int(match.group(2))
            return rep
        except ValueError:
            return match.group(3)


    def parenthesis(self, line):
        """It returns content inside parenthesis"""

        pin = 0
        buf = ''
        vector = {'(': 1, ')': -1}
        for char in line:
            if char in vector:
                pin += vector[char]
            if pin == 0 and len(buf):
                return buf
            if pin > 0:
                buf += char


    def resolve(self, source):
        """Source first pass"""

        new = []
        source = re.sub(r"('|\"){3}\n*(.+\n)*('|\"){3}", '', source, re.MULTILINE)
        source = re.sub(r'(\s|\()(\d+)([a-gA-G][0-9]|\.)', self.repeat, source)
        for line in iter(source.splitlines()):
            while '(' in line:
                pattern = r'' + self.parenthesis(line)[1:]
                pattern = pattern.replace(r'(', r'\(').replace(r')', r'\)').replace(r'*', r'\*')
                line = re.sub(r'(\s|\()(s*\d*)\((' + pattern + r')\)', self.repeat, line)
            new.append(line)
        return '\n'.join(new)
