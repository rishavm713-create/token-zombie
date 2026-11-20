"""Basic statistics. All functions take a non-empty list of numbers."""
import math


def mean(xs):
    return sum(xs) / len(xs)


def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2]  # BUG 1: even-length lists must average the two middle values


def mode(xs):
    counts = {}
    for x in xs:
        counts[x] = counts.get(x, 0) + 1
    best = max(counts.values())
    return min(k for k, v in counts.items() if v == best)


def variance(xs):
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / len(xs)  # BUG 2: sample variance divides by n-1 (n>1)


def stdev(xs):
    return math.sqrt(variance(xs))


def percentile(xs, p):
    s = sorted(xs)
    k = int(round((len(s) - 1) * p / 100))  # BUG 3: must interpolate linearly between neighbours
    return s[k]
