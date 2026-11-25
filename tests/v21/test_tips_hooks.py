# tztips wired into the live hooks and the tz CLI.
import os, sys, json, tempfile, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Z, ok, done, guard

HOME = tempfile.mkdtemp()
PROJ = os.path.join(HOME, 'proj'); os.makedirs(PROJ)
os.makedirs(os.path.join(HOME, 'app', '.git'))
dated = lambda: [f for f in (os.listdir(os.path.join(PROJ, 'handoffs')) if os.path.isdir(os.path.join(PROJ, 'handoffs')) else []) if f.startswith('20')]


def chat(name, size, tools=0, model='claude-opus-5-5'):
    p = os.path.join(HOME, name + '.jsonl')
    u = lambda n: {'type': 'assistant', 'message': {'model': model, 'usage': {'input_tokens': n}, 'content': []}}
    rows = [u(1000), u(size)]
    for i in range(tools):
        rows.append({'type': 'assistant', 'message': {'model': model, 'content': [
            {'type': 'tool_use', 'id': f't{i}', 'name': 'Read', 'input': {'file_path': f'/x/{i}'}}]}})
    open(p, 'w').write('\n'.join(map(json.dumps, rows)) + '\n')
    return p


def prompt(sid, text, path, env=None, cwd=PROJ):
    o, _ = guard({'hook_event_name': 'UserPromptSubmit', 'session_id': sid, 'prompt': text, 'cwd': cwd,
                  'transcript_path': path}, env, HOME)
    return o, ((o.get('hookSpecificOutput') or {}).get('additionalContext') or '')


big = chat('big', 160000)
# hard cap: off by default
o, c = prompt('s0', 'please continue the parser work', big)
ok('size gate off by default', 'Fresh chat' not in c or 'mcp__ccd_turn__wrap_up' not in c)
GATE = {'TZ_FEAT_SIZE_GATE': '1'}
o, c = prompt('s1', 'please continue the parser work', big, GATE)
ok('cap off by default', o.get('decision') != 'block')
ok('size tier advice instead', 'Fresh chat' in c)
ok('no handoff written when off', not dated())
ON = {'TZ_FEAT_SIZE_CAP': '1'}
o, _ = prompt('s2', 'please continue the parser work', big, ON)
ok('cap blocks when on', o.get('decision') == 'block')
r = o.get('reason', '')
ok('block reason', '/clear now; handoff saved' in r and 'TZ_FEAT_SIZE_CAP=0' in r)
hs = dated()
ok('handoff saved before block', len(hs) == 1 and 'size cap' in open(os.path.join(PROJ, 'handoffs', hs[0])).read())
for t in ('/clear', '/compact keep notes', 'Fresh chat'):
    o, _ = prompt('s2', t, big, ON)
    ok('way out passes: ' + t, o.get('decision') != 'block')
o, _ = prompt('s2b', 'go on', chat('compacted', 160000) , dict(ON, TZ_SIZE_CAP='200000'))
ok('cap threshold configurable', o.get('decision') != 'block')
p = chat('after', 160000); open(p, 'a').write(json.dumps({'type': 'system', 'subtype': 'compact_boundary'}) + '\n')
o, _ = prompt('s2c', 'go on', p, ON)
ok('no block right after compaction', o.get('decision') != 'block')

# soft tiers: once per tier
mid = chat('mid', 60000)
_, c = prompt('s3', 'add a retry to the uploader', mid, GATE)
ok('soft 50k speaks', 'mcp__ccd_turn__wrap_up' in c)
_, c = prompt('s3', 'add a retry to the uploader too', mid, GATE)
ok('soft 50k only once', 'mcp__ccd_turn__wrap_up' not in c)
_, c = prompt('s3off', 'add a retry to the uploader', mid, {'TZ_FEAT_SIZE_GATE': '0'})
ok('size gate off: quiet', 'mcp__ccd_turn__wrap_up' not in c)

small = chat('small', 3000)
_, c = prompt('s4', 'hello', small, cwd=HOME)
ok('home cwd speaks', 'started in ~' in c)
_, c2 = prompt('s4', 'hello again', small, cwd=HOME)
ok('home cwd once', 'started in ~' not in c2)
_, c = prompt('s5', 'data row\n' * 2000, small)
ok('paste warn', 'paste' in c.lower())
_, c = prompt('s6', 'hello there', small, {'TZ_FEAT_PASTE_WARN': '0'})
ok('quiet on a plain prompt', 'paste' not in c.lower())
prompt('s7', 'fix the login button colour in src/auth/login.tsx styles', small)
st = open(os.path.join(HOME, '.claude', 'token-zombie', 'tips-s7.json')).read()
ok('state keeps words, not the raw prompt', 'login' in st and 'fix the login button colour in' not in st)

# bulk reads
def pre(sid, path, tool='Read', env=None, **kw):
    o, _ = guard(dict({'hook_event_name': 'PreToolUse', 'session_id': sid, 'tool_name': tool, 'cwd': PROJ,
                       'tool_input': {'pattern': 'x'} if tool != 'Read' else {'file_path': '/nonexistent'},
                       'transcript_path': path}, **kw), env, HOME)
    h = o.get('hookSpecificOutput') or {}
    return h.get('permissionDecision'), h.get('permissionDecisionReason', '')


many = chat('many', 3000, tools=8)
BON = {'TZ_FEAT_BULK_READ_BLOCK': '1'}
ok('bulk off by default', pre('b0', many, 'Grep')[0] != 'deny')
d, why = pre('b1', many, 'Grep', BON)
ok('bulk blocks grep', d == 'deny' and 'Explore' in why)
ok('retry passes (no lock-out)', pre('b1', many, 'Grep', BON)[0] != 'deny')
ok('bulk blocks Read too', pre('b2', many, 'Read', BON)[0] == 'deny')
ok('subagent never blocked', pre('b3', many, 'Grep', BON, agent_id='a1')[0] != 'deny')
ok('short streak passes', pre('b4', chat('few', 3000, tools=3), 'Glob', BON)[0] != 'deny')

# SessionStart
os.makedirs(os.path.join(HOME, '.claude'), exist_ok=True)
open(os.path.join(HOME, '.claude', 'CLAUDE.md'), 'w').write('\n'.join(f'rule {i}: keep the output short and plain' for i in range(600)))
open(os.path.join(HOME, '.claude', 'settings.json'), 'w').write('{}')


def start(sid, env=None):
    r = subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tz-start.py')], capture_output=True, text=True, timeout=30,
                       input=json.dumps({'session_id': sid, 'cwd': PROJ, 'source': 'startup'}),
                       env=dict(os.environ, HOME=HOME, TZ_FRESH_BG='0', **(env or {})))
    return r.stdout


out = start('i1')
ok('start: instr advice', 'tz instr --fix' in out)
ok('start: no defaults offer by default', 'tz defaults' not in out)
_, c = prompt('i1', 'hello', small)
ok('instr said once per chat', 'tz instr --fix' not in c)
ok('instr switchable', 'tz instr --fix' not in start('i2', {'TZ_FEAT_INSTR_ADVICE': '0'}))
settings = open(os.path.join(HOME, '.claude', 'settings.json')).read()
ok('defaults offer once ever', 'tz defaults' in start('i3', {'TZ_FEAT_DEFAULTS_ADVICE': '1'})
   and 'tz defaults' not in start('i4', {'TZ_FEAT_DEFAULTS_ADVICE': '1'}))
ok('offer never edits settings', open(os.path.join(HOME, '.claude', 'settings.json')).read() == settings)


def tz(*a):
    r = subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tz'), *a], capture_output=True, text=True, timeout=30,
                       cwd=PROJ, env=dict(os.environ, HOME=HOME))
    return r.returncode, r.stdout + r.stderr


for args in (('tips', 'instr'), ('instr',), ('defaults',), ('stats', '--breakdown', big), ('stats', '--breakdown'), ('config',)):
    rc, out = tz(*args)
    ok('tz ' + ' '.join(args[:2]), rc == 0 and out.strip() and 'Traceback' not in out)
ok('tz defaults is a dry run', open(os.path.join(HOME, '.claude', 'settings.json')).read() == settings)
rc, out = tz('defaults', 'apply', '--yes')
ok('tz defaults apply', rc == 0 and open(os.path.join(HOME, '.claude', 'settings.json')).read() != settings)
rc, out = tz('defaults', 'restore')
ok('tz defaults restore', rc == 0 and json.loads(open(os.path.join(HOME, '.claude', 'settings.json')).read()) == {})

import tzcont
line = tzcont.idle_advice({}, 50000, 900, 300)
ok('idle: one line with offer', 'Fresh chat' in line and 'likely expired' in line and '\n' not in line)
os.environ['TZ_FEAT_IDLE_COST'] = '0'
ok('idle offer switchable', 'Fresh chat' not in tzcont.idle_advice({}, 50000, 900, 300))
import tzlib
ok('list config value', tzlib.cfg('size_soft') == [50000, 100000])
ok('blockers default off', not any(tzlib.FEATURES[f] for f in ('size_gate', 'size_cap', 'bulk_read_block', 'defaults_advice')))
done()
