# tzbudget (budget warning ladder, adapted from ruvnet/ruflo): parity cases, log scan, rung memory, opt-in block, CLI.
import datetime as dt, json, os, subprocess, sys, tempfile, time
HOME = tempfile.mkdtemp()
os.environ['HOME'] = HOME
os.environ['USERPROFILE'] = os.environ['HOME']  # Windows expanduser reads this one
for k in [k for k in os.environ if k.startswith('TZ_')]:
    del os.environ[k]
from harness import ok, done, Z
import tzbudget as B
import tzlib

# --- upstream parity (budget.ts / budget.mjs thresholds)
for u, want in ((0, 'OK'), (0.49, 'OK'), (0.5, 'INFO'), (0.74, 'INFO'), (0.75, 'WARNING'), (0.89, 'WARNING'), (0.9, 'CRITICAL'),
                (0.999, 'CRITICAL'), (1.0, 'HARD_STOP'), (3, 'HARD_STOP')):
    ok('level %s' % u, B.alert_level(u) == want)
ok('budgetOf off values', all(B.budget_of(x) is None for x in ('0', 0, -1, 'abc', '', None, True, float('inf'), float('nan'), 'inf', [5])))
ok('budgetOf numbers', B.budget_of('12.5') == 12.5 and B.budget_of(7) == 7)
ok('same rung silent', not B.is_raised('WARNING', 'WARNING'))
ok('lower rung silent', not B.is_raised('CRITICAL', 'INFO'))
ok('higher rung speaks', B.is_raised('INFO', 'CRITICAL'))

# --- per-run ladder (tz agent --budget)
os.environ['TZ_FEAT_BUDGET_WARN'] = '1'
ok('run below half', B.run_note(0, 400, 1000) == '')
ok('run reaches half', 'INFO' in B.run_note(400, 500, 1000))
ok('run same rung silent', B.run_note(500, 700, 1000) == '')
ok('run jump names top rung', 'HARD_STOP' in B.run_note(500, 1200, 1000))
ok('run no budget', B.run_note(0, 10**9, 0) == '')
os.environ['TZ_FEAT_BUDGET_WARN'] = '0'
ok('run feature off', B.run_note(400, 500, 1000) == '')
os.environ['TZ_FEAT_BUDGET_WARN'] = '1'

# --- log scan
NOW = time.time()
proj = os.path.join(HOME, '.claude', 'projects', '-p')
os.makedirs(os.path.join(proj, 's1', 'subagents'))
log = os.path.join(proj, 's1.jsonl')


def reply(mid, tok, days_ago=0, model='claude-sonnet-x', **usage):
    ts = dt.datetime.fromtimestamp(NOW - days_ago * 86400, dt.timezone.utc).isoformat()
    return json.dumps({'timestamp': ts, 'message': {'id': mid, 'model': model, 'usage': dict({'input_tokens': tok}, **usage)}}) + '\n'


def add(path, text):
    with open(path, 'a') as f:
        f.write(text)


def spent(key='session_tokens', limit=1000):
    return B.status(log, {key: limit}, now=NOW)[0]['spent']


add(log, reply('a', 100) + reply('a', 100))
ok('repeated id counted once', spent() == 100)
add(log, reply('a', 100) + reply('b', 50))
ok('id repeated across scans counted once', spent() == 150)
half = reply('c', 25)
add(log, half[:20])
ok('unfinished line waits', spent() == 150)
add(log, half[20:])
ok('finished line counted', spent() == 175)
add(os.path.join(proj, 's1', 'subagents', 'agent-1.jsonl'), reply('d', 25, output_tokens=0, cache_read_input_tokens=100))
ok('subagent and cache tokens counted', spent() == 300)
usd = os.path.join(proj, 'u.jsonl')
add(usd, reply('u1', 0, cache_creation_input_tokens=1000000, cache_creation={'ephemeral_1h_input_tokens': 1000000}))
want = B.tzprice.cost_usd('claude-sonnet-x', 0, 0, 0, 0, 1000000)
ok('usd uses shared price table', abs(B.status(usd, {'session_usd': 10}, now=NOW)[0]['spent'] - want) < 1e-9)
os.remove(usd)
other = os.path.join(proj, 's2.jsonl')
add(other, reply('e', 200, days_ago=3) + reply('f', 5000, days_ago=9))
ok('week sums all chats, drops old days', spent('week_tokens') == 500)
ok('chat scope ignores other chats', spent() == 300)
ok('cached log needs no read even past deadline', B.status(other, {'session_tokens': 10}, deadline=1, now=NOW)[0]['partial'] is False)
os.remove(os.path.join(HOME, '.claude', 'token-zombie', 'budget.json'))
r = B.status(log, {'session_tokens': 10}, deadline=1, now=NOW)[0]
ok('cold scan past deadline is partial', r['partial'] and r['spent'] == 0 and 'partial' in B.line(r))
ok('missing log is unknown, not zero', B.status('/nope', {'session_tokens': 10}, now=NOW) == [])
add(log, '')
open(log, 'w').write(reply('z', 10))
ok('shrunk log rescanned', spent() == 135)  # 10 main + 125 subagent

# --- rung memory (dispatcher advice)
open(log, 'w').write(reply('g', 400))
os.remove(os.path.join(proj, 's1', 'subagents', 'agent-1.jsonl'))
os.remove(os.path.join(HOME, '.claude', 'token-zombie', 'budget.json'))
D = {'session_id': 's1', 'transcript_path': log, 'prompt': 'go on', 'cwd': tempfile.mkdtemp()}
ok('no budget: silent, no state', B.prompt_advice(D, NOW) == '' and not os.path.exists(os.path.join(HOME, '.claude', 'token-zombie', 'budget.json')))
os.environ['TZ_BUDGET_SESSION_TOKENS'] = '1000'
ok('under half silent', B.prompt_advice(D, NOW) == '')
add(log, reply('h', 150))
m = B.prompt_advice(D, NOW)
ok('first rung told', 'INFO' in m and '550 of 1,000' in m and '[actual' in m)
ok('told once', B.prompt_advice(D, NOW) == '')
add(log, reply('i', 400))
ok('next rung told', 'CRITICAL' in B.prompt_advice(D, NOW))
ok('other chat has own ladder', 'CRITICAL' in B.prompt_advice(dict(D, session_id='s9'), NOW))
os.environ['TZ_BUDGET_SESSION_TOKENS'] = '1100'
ok('new limit, new ladder', 'WARNING' in B.prompt_advice(D, NOW))
os.environ['TZ_FEAT_BUDGET_WARN'] = '0'
os.environ['TZ_BUDGET_SESSION_TOKENS'] = '100'
ok('warn feature off is silent', B.prompt_advice(D, NOW) == '')
os.environ['TZ_FEAT_BUDGET_WARN'] = '1'
del os.environ['TZ_BUDGET_SESSION_TOKENS']
os.environ['TZ_BUDGET_WEEK_TOKENS'] = '1000'
ok('week told', 'last 7 days' in B.prompt_advice(D, NOW))
ok('week shared across chats', B.prompt_advice(dict(D, session_id='s9'), NOW) == '')
B.prompt_advice(D, NOW + 30 * 86400)  # window rolled off
ok('week warns again after reset', B.prompt_advice(D, NOW) != '')
del os.environ['TZ_BUDGET_WEEK_TOKENS']

# --- opt-in block
os.environ['TZ_BUDGET_SESSION_TOKENS'] = '100'
ok('block default off', B.block_reason(D, NOW) == '' and not tzlib.FEATURES.get('budget_block', 0))
os.environ['TZ_FEAT_BUDGET_BLOCK'] = '1'
why = B.block_reason(D, NOW)
notes = os.path.join(D['cwd'], 'handoffs')
ok('block at hard stop saves handoff', 'HARD_STOP' in why and 'handoff saved' in why and len(os.listdir(notes)) == 1)
B.block_reason(D, NOW)
ok('handoff saved once', open(os.path.join(notes, os.listdir(notes)[0])).read().count('spend budget stop') == 1)
ok('slash passes', B.block_reason(dict(D, prompt='/clear'), NOW) == '')
ok('fresh chat passes', B.block_reason(dict(D, prompt='Fresh chat.'), NOW) == '')
os.environ['TZ_BUDGET_SESSION_TOKENS'] = '100000'
ok('no block under budget', B.block_reason(D, NOW) == '')
os.environ['TZ_FEAT_BUDGET_BLOCK'] = '0'
del os.environ['TZ_BUDGET_SESSION_TOKENS']

# --- CLI
cfg_path = os.path.join(HOME, '.claude', 'token-zombie', 'config.json')
json.dump({'mode': 'full', 'limit': 123}, open(cfg_path, 'w'))


def cli(*a):
    return subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tzbudget.py'), *a], capture_output=True, text=True, cwd=D['cwd'], timeout=30)


ok('cli off', 'no budget set' in cli().stdout)
ok('cli set keeps config', cli('set', 'week_tokens', '100').returncode == 0 and json.load(open(cfg_path)) == {'mode': 'full', 'limit': 123, 'budget': {'week_tokens': 100.0}})
c = cli('check')
ok('cli check exits 1 at hard stop', c.returncode == 1 and 'HARD_STOP' in c.stdout)
ok('cli show exits 0', cli().returncode == 0)
ok('cli rejects zero and bad key', cli('set', 'week_tokens', '0').returncode == 2 and cli('set', 'nope', '5').returncode == 2)
ok('cli set off', cli('set', 'week_tokens', 'off').returncode == 0 and json.load(open(cfg_path))['budget'] == {})
open(cfg_path, 'w').write('{broken')
ok('broken config not clobbered', cli('set', 'week_usd', '5').returncode == 2 and open(cfg_path).read() == '{broken')
done()
