from __future__ import \
    division, unicode_literals, print_function, absolute_import

import sys
import os

try:
    from traceplot import plot
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from traceplot import plot


def main():
    if len(sys.argv) != 2:
        usage()
        sys.exit(1)

    if '-h' in sys.argv or '--help' in sys.argv:
        usage()
        sys.exit()

    filename = sys.argv[1]

    try:
        with open(filename) as f:
            plot.main(f)
    except IOError as e:
        print('Error: {}'.format(e))
        sys.exit(1)


def usage():
    print('Usage: {} <trace_file>'.format(sys.argv[0]))


if __name__ == '__main__':
    main()
