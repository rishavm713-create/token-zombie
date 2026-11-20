#!/usr/bin/env python3
# Zombie mascot: state is a pure function of the status bus dict. Frames: ASCII + SVG + one emoji for the statusline.
STATES = ('CHOMP', 'HAPPY', 'ALERT', 'SLEEP', 'CELEBRATE')
EMOJI = {'CHOMP': '🧟', 'HAPPY': '😊', 'ALERT': '🚨', 'SLEEP': '😴', 'CELEBRATE': '🎉'}
ASCII = {'CHOMP': '(x_x) nom nom', 'HAPPY': '(^_^)', 'ALERT': '(O_O)!', 'SLEEP': '(-_-) zzz', 'CELEBRATE': '\\(^o^)/'}
EYES = {'CHOMP': 'x x', 'HAPPY': '^ ^', 'ALERT': 'O O', 'SLEEP': '- -', 'CELEBRATE': '* *'}


def mascot_state(s):
    """s = status bus dict (may be empty). ALERT beats everything; SLEEP when no data or idle; CELEBRATE right after a task closed."""
    if not s or not s.get('ts'):
        return 'SLEEP'
    if s.get('level') in ('CRITICAL', 'EXHAUSTED', 'APPROACHING LIMIT') or s.get('risk') == 'high':
        return 'ALERT'
    if s.get('task_just_done'):
        return 'CELEBRATE'
    if s.get('level') == 'ELEVATED' or s.get('activity') == 'working':  # activity only 'working' when hook-measured
        return 'CHOMP'
    return 'HAPPY' if s.get('level') == 'NORMAL' else 'SLEEP'


def svg(state):
    e = EYES[state].split()
    mouth = {'CHOMP': 'M30 62 L40 70 L50 62 L60 70 L70 62', 'ALERT': 'M40 66 a10 8 0 1 0 20 0 a10 8 0 1 0 -20 0',
             'SLEEP': 'M40 66 L60 66', 'HAPPY': 'M35 62 Q50 78 65 62', 'CELEBRATE': 'M32 60 Q50 85 68 60'}[state]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="96" height="96" role="img" aria-label="mascot {state}">'
            f'<circle cx="50" cy="50" r="42" fill="#7fb069" stroke="#2f4f2f" stroke-width="3"/>'
            f'<text x="34" y="46" font-size="14" text-anchor="middle">{e[0]}</text><text x="66" y="46" font-size="14" text-anchor="middle">{e[1]}</text>'
            f'<path d="{mouth}" fill="none" stroke="#2f4f2f" stroke-width="3"/></svg>')


def main(argv):
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import tzbus
    s = tzbus.read_bus()
    st = mascot_state(s)
    print(f'{EMOJI[st]} {st} {ASCII[st]}')
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv[1:]))
