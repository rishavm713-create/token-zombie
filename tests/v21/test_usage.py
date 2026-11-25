# v2.1 group G parity: ccstatusline usable-context %, cache hit rate, ccusage 5h blocks (rebuilt, MIT originals).
import os, sys
from harness import ok, done, Z
sys.path.insert(0, os.path.join(Z, 'bin'))
import tzusage as U

os.environ.pop('CLAUDE_AUTOCOMPACT_PCT_OVERRIDE', None)
ok('usable 200k/80k = 160k, 50.0%', U.usable(80000, 200000) == (160000, 50.0))
ok('usable caps at 100', U.usable(190000, 200000)[1] == 100.0)
os.environ['CLAUDE_AUTOCOMPACT_PCT_OVERRIDE'] = '50'
ok('override lowers to 50%', U.usable(50000, 200000) == (100000, 50.0))
os.environ['CLAUDE_AUTOCOMPACT_PCT_OVERRIDE'] = '95'
ok('override cannot raise above 80%', U.usable(80000, 200000)[0] == 160000)
os.environ.pop('CLAUDE_AUTOCOMPACT_PCT_OVERRIDE')
ok('hit rate read/(read+write)', U.hit_rate(900, 100) == 90.0 and U.hit_rate(0, 0) is None)

h = 3600
T = 1_700_000_000 - 1_700_000_000 % h  # an hour boundary
b = U.blocks([(T, 10), (T + 5 * h, 20)], now=T + 100 * h)  # ccusage: exactly 5h from start stays one block
ok('5h exactly stays one block', len(b) == 1 and b[0]['tokens'] == 30)
b = U.blocks([(T, 10), (T + 5 * h + 1, 20)], now=T + 100 * h)
ok('just past 5h splits', len([x for x in b if not x['gap']]) == 2)
b = U.blocks([(T + 600, 10), (T + 12 * h, 20)], now=T + 100 * h)
ok('long gap inserts gap block', [x['gap'] for x in b] == [False, True, False])
ok('block start floored to hour', b[0]['start'] == T and b[0]['end'] == T + 5 * h)
b = U.blocks([(T, 100), (T + 600, 100)], now=T + 1200)
ok('active block, burn 20/min, projection grows', b[0]['active'] and abs(b[0]['burn'] - 20) < 1e-6 and b[0]['projected'] == 200 + 20 * (5 * h - 1200) // 60)
done()
