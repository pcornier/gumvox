import sys
from lib.parser import Parser
from lib.resolver import Resolver

def main(argv):

    usage = 'main.py <inputfile> <outputfile>'
    inf = ''
    out = ''

    if len(argv) == 2:
        inf, out = argv

    else:
        print(usage)
        sys.exit(2)

    try:
        fpt = open(inf, 'r')
        source = fpt.read()

    except IOError:
        print('Cannot open', inf)
        sys.exit(2)

    source = Resolver().resolve(source)
    project = Parser().parse(source)
    with open(out, 'wb') as fpt:
        project.write_to(fpt)


if __name__ == '__main__':
    main(sys.argv[1:])
