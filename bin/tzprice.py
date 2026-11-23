#!/usr/bin/env python3
# ONE pricing table for TOKEN ZOMBIE. All values are EST list prices (USD per 1M tokens), not billing data.
# Override: ~/.claude/token-zombie/prices.json, e.g. {"prices": {"sonnet": [3, 15]}, "cache": {"read": 0.1}}
import json, os, sys

AS_OF = '2026-11-23'
LABEL = 'EST list price'
PRICES = {'opus': (5.0, 25.0), 'sonnet': (3.0, 15.0), 'haiku': (1.0, 5.0),
          'fable': (5.0, 25.0)}  # fable: no price known to the old code; assumed = opus [EST], override in prices.json
CACHE = {'read': 0.1, 'write_5m': 1.25, 'write_1h': 2.0}  # multipliers on the input price
DEFAULT = 'sonnet'


def path():
    return os.path.join(os.path.expanduser('~'), '.claude', 'token-zombie', 'prices.json')


def _load():
    """Merge the user override into PRICES / CACHE in place; bad or missing JSON is ignored."""
    try:
        with open(path()) as f:
            d = json.load(f)
        if not isinstance(d, dict):
            return
        for k, v in (d.get('prices') or {}).items():
            if isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
                PRICES[str(k).lower()] = (float(v[0]), float(v[1]))
        for k, v in (d.get('cache') or {}).items():
            if k in CACHE and isinstance(v, (int, float)) and not isinstance(v, bool):
                CACHE[k] = float(v)
    except Exception:
        pass


_load()


def family(model_id):
    m = (model_id or '').lower()
    return next((k for k in PRICES if k in m), DEFAULT)


def price(model_id):
    return PRICES[family(model_id)]


def cost_usd(model_id, input, output, cache_read=0, cache_write_5m=0, cache_write_1h=0):
    pin, pout = price(model_id)
    ie = input + CACHE['read'] * cache_read + CACHE['write_5m'] * cache_write_5m + CACHE['write_1h'] * cache_write_1h
    return (ie * pin + output * pout) / 1e6


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    js = '--json' in a
    a = [x for x in a if x != '--json']
    if a and a[0] == 'price':
        a = a[1:]
    fams = {family(a[0]): PRICES[family(a[0])]} if a else dict(PRICES)
    if js:
        print(json.dumps(dict(label=LABEL, as_of=AS_OF, unit='USD per Mtok (in, out)', prices={k: list(v) for k, v in fams.items()},
                              cache=CACHE, override_file=path(), override_exists=os.path.exists(path()))))
        return 0
    print(f'PRICES [{LABEL}, as_of {AS_OF}] USD per Mtok')
    for k, (i, o) in fams.items():
        print(f'  {k:8} in {i:g}  out {o:g}')
    print(f"cache multipliers on input: read {CACHE['read']:g}x, write 5m {CACHE['write_5m']:g}x, write 1h {CACHE['write_1h']:g}x")
    print(f"override file: {path()} ({'found' if os.path.exists(path()) else 'not present'})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
