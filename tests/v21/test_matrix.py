# Combination and conflict checks over the shared offline matrix (tz bench matrix, 1 trial, real hook dispatcher).
# Conflict rule (V2.1-PLAN): all features on must be at least as good as each feature alone and as TZ 2.0,
# with no false positives; removing any one feature must not make the run better (else it conflicts).
from harness import ok, done
import tzmatrix as M
from tzlib import FEATURES

A = [n for n, _ in M.arms()]
n = len(FEATURES)
ok('arm count = off, tz20, only x n, all, all-minus x n, all-minus-conflicts', len(A) == 2 * n + 4)
ok('arms named', {'off', 'tz20', 'all', 'all-minus-conflicts'} <= set(A))
ok('no conflicts declared', M.CONFLICTS == [])

rep = M.run(1, {'read_guard': 'deny'})
R = {r['arm']: r for r in rep['rows']}
net = {a: r['total']['saved'] - r['total']['injected'] for a, r in R.items()}
ok('label says provider tokens unknown', 'UNKNOWN' in rep['label'])
ok('all: no false positives', R['all']['total']['fp'] == 0)
ok('all: no false negatives', R['all']['total']['fn'] == 0)
ok('all beats TZ 2.0 on net chars', net['all'] > net['tz20'])
ok('TZ 2.0 idle_1h false positive is the measured gap', R['tz20']['scenarios']['idle_1h']['fp'] == 1)
for f in FEATURES:
    ok(f'all >= only:{f} (net)', net['all'] >= net[f'only:{f}'])
    # conflict = removing f improves quality (fewer fp/fn) or lets other features save more; f's own advice chars are overhead, reported not failed
    m, a = R[f'all-minus:{f}']['total'], R['all']['total']
    ok(f'all-minus:{f}: no conflict', m['fp'] >= a['fp'] and m['fn'] >= a['fn']
       and m['saved'] <= a['saved'])
ok('stuck_detect overhead small (<=200 chars, measured)', R['all']['total']['injected'] - R['all-minus:stuck_detect']['total']['injected'] <= 200)
ok('all-minus-conflicts == all (empty list)', net['all-minus-conflicts'] == net['all'])
ok('safety: all blocks every labelled bad command', R['all']['scenarios']['safety']['fn'] == 0)
ok('off arm: TZ silent on safety (mode off)', R['off']['scenarios']['safety']['fp'] == 0)
sc = lambda a, s: R[a]['scenarios'][s]
ok('saved is gross (injected subtracted once): mcp_dup', sc('all', 'mcp_dup')['saved'] == 3000)
ok('deny -> full retry saves nothing, costs only the deny text', sc('tz20', 'dup_read')['saved'] == 0 and sc('tz20', 'dup_read')['injected'] > 0)

old = M.run(2, {'read_guard': 'deny'}, v040=True)
O = {r['arm']: r for r in old['rows']}
ok('v040 arm added and guard restored', 'v040' in O and M.GUARD.startswith(M.B))
ok('trial variance recorded', all({'net_min', 'net_max', 'net_sd', 'fp', 'fn'} <= set(r['trial_variance']) for r in old['rows']))
ok('report shows variance', 'net min..max' in M.markdown(old))
done()
