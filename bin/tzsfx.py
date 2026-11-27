#!/usr/bin/env python3
"""Generate the Mod's mode-switch sound effects (sounds/mode-*.wav). Deterministic; stdlib only.
Usage: python3 bin/tzsfx.py [out_dir]   (default: <repo>/sounds)"""
import math, os, struct, sys, wave

RATE = 22050
# per mode: list of (freq Hz, seconds); off falls, lite one blip, full rises, ultra rises fast to a high note
NOTES = {
    'off': [(660, .08), (440, .08), (294, .14)],
    'lite': [(784, .12)],
    'full': [(523, .08), (784, .14)],
    'ultra': [(523, .06), (659, .06), (784, .06), (1047, .16)],
}


def tone(f, s, gain=.35):
    n = int(RATE * s)
    out = []
    for i in range(n):
        env = min(1, i / 200) * min(1, (n - i) / (n * .6))  # short attack, soft tail: no clicks
        # square-ish zombie buzz: sine + a little 3rd harmonic
        v = math.sin(2 * math.pi * f * i / RATE) + .25 * math.sin(6 * math.pi * f * i / RATE)
        out.append(int(32767 * gain * env * v / 1.25))
    return out


def groan():
    """Zombie groan for a mascot click: low voice (95 -> 55 Hz) with a slow wobble, rough harmonics, a little noise. Deterministic."""
    n, seed, ph, out = int(RATE * 1.1), 12345, 0.0, []
    for i in range(n):
        t = i / RATE
        f = 95 - 40 * (t / 1.1) + 6 * math.sin(2 * math.pi * 7 * t)
        ph += 2 * math.pi * f / RATE
        seed = (seed * 1103515245 + 12345) & 0x7fffffff
        noise = seed / 0x7fffffff - .5
        v = math.sin(ph) + .6 * math.sin(2 * ph) + .4 * math.sin(3 * ph) + .25 * noise
        env = min(1, i / 1500) * min(1, (n - i) / (n * .45))
        out.append(int(32767 * .45 * env * v / 2.2))
    return out


def main(out):
    os.makedirs(out, exist_ok=True)
    for mode, notes in NOTES.items():
        pcm = [x for f, s in notes for x in tone(f, s)]
        with wave.open(os.path.join(out, f'mode-{mode}.wav'), 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(struct.pack(f'<{len(pcm)}h', *pcm))
    pcm = groan()
    with wave.open(os.path.join(out, 'groan.wav'), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(struct.pack(f'<{len(pcm)}h', *pcm))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sounds'))
