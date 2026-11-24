# cache_ttl_auto (measured 1 h cache) + dup_skeleton (deny carries a line-numbered outline).
import os, json, tempfile, importlib
from harness import ok, done, guard, Z
H = tempfile.mkdtemp(); os.environ['HOME'] = H
import tzcont, tzcompress
d = tempfile.mkdtemp()
p1, p2 = os.path.join(d, 'a.jsonl'), os.path.join(d, 'b.jsonl')
open(p1, 'w').write(json.dumps({'message': {'id': 'a', 'usage': {'input_tokens': 1, 'cache_creation': {'ephemeral_1h_input_tokens': 900}}}}) + '\n')
open(p2, 'w').write(json.dumps({'message': {'id': 'a', 'usage': {'input_tokens': 1, 'cache_creation': {'ephemeral_5m_input_tokens': 900}}}}) + '\n')
ok('1h writes -> ttl 3600', tzcont.cache_ttl(p1) == 3600)
ok('5m writes -> ttl 300', tzcont.cache_ttl(p2) == 300)
ok('no log -> default 300', tzcont.cache_ttl(None) == 300 and tzcont.cache_ttl('/nope') == 300)
ok('15 min idle, 1h cache: no expiry advice (was a false positive)', tzcont.idle_advice({}, 50000, 900, 3600) == '')
ok('15 min idle, 5m cache: expiry advice', 'expired' in tzcont.idle_advice({}, 50000, 900, 300))
ok('2 h idle, 1h cache: expiry advice', 'expired' in tzcont.idle_advice({}, 50000, 7200, 3600))
os.environ['TZ_CACHE_TTL'] = '120'; ok('explicit TZ_CACHE_TTL wins', tzcont.cache_ttl(p1) == 120); del os.environ['TZ_CACHE_TTL']
os.environ['TZ_FEAT_CACHE_TTL_AUTO'] = '0'; ok('feature off -> fixed ttl', tzcont.cache_ttl(p1) == 300); del os.environ['TZ_FEAT_CACHE_TTL_AUTO']
# stay_or_fresh: warm 1h cache after 15 min idle must not charge a cache re-write
a = tzcont.stay_or_fresh(80000, 20000, 6, 3, 900, 40, 0.0, 3600)
b = tzcont.stay_or_fresh(80000, 20000, 6, 3, 900, 40, 0.0, 300)
ok('stay_or_fresh mentions expiry only for the 5m cache', 'expired' not in a and 'expired' in b)
# outline
o = tzcompress.outline(os.path.join(Z, 'bin', 'tzab.py'))
ok('py outline has line spans', 'def run_session' in o and o.startswith('L'))
ok('outline capped', len(tzcompress.outline(os.path.join(Z, 'bin', 'tzcont.py'), cap=300)) <= 330)
md = os.path.join(d, 'x.md'); open(md, 'w').write('# T\ntext\n## Sub\n')
ok('md outline = headings', tzcompress.outline(md) == 'L1 # T\nL3 ## Sub')
sh = os.path.join(d, 'x.sh'); open(sh, 'w').write('# comment\necho hi\n')
ok('shell comments are not headings', tzcompress.outline(sh) == '')
js = os.path.join(d, 'x.js'); open(js, 'w').write('export async function go(a) {\n}\nconst f = (x) => x\nclass K {}\n')
ok('js outline', tzcompress.outline(js) == 'L1 export async function go(a) {\nL3 const f = (x) => x\nL4 class K {}')
# end-to-end: deny mode, second identical Read of a >= 2000-char file -> deny with outline (through the dispatcher)
os.makedirs(os.path.join(H, '.claude', 'token-zombie'), exist_ok=True)
open(os.path.join(H, '.claude', 'token-zombie', 'config.json'), 'w').write('{"read_guard":"deny"}')
big = os.path.join(d, 'big.py'); open(big, 'w').write(''.join(f'def f{i}(x):\n    return x + {i}\n\n' for i in range(120)))
pl = {'hook_event_name': 'PreToolUse', 'session_id': 'dupt', 'tool_name': 'Read', 'tool_input': {'file_path': big}}
post = dict(pl, hook_event_name='PostToolUse', tool_response={'file': {'content': open(big).read()}})
env = {'TZ_DEDUPE': '0'}
guard(pl, env, H); guard(post, env, H)
r, _ = guard(pl, env, H)
hs = r.get('hookSpecificOutput', {})
ok('2nd read denied', hs.get('permissionDecision') == 'deny')
ok('deny carries outline', 'Outline' in hs.get('permissionDecisionReason', '') and 'L1-2 def f0' in hs.get('permissionDecisionReason', ''))
r2, _ = guard(pl, env, H)
ok('identical retry allowed', r2.get('hookSpecificOutput', {}).get('permissionDecision') != 'deny')
done()
