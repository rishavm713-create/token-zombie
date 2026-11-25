# tz toolprune + mcp_dup: fake transcripts in a temp HOME; parity with TokenEconomizer test_live_hooks (never-used tools proposed,
# used tool kept, high-risk 3x, apply/restore byte-identical with user entry kept) plus protected set and mcp_dup cases.
import os, json, tempfile, time
from harness import ok, done
H = tempfile.mkdtemp(); os.environ['HOME'] = H; os.environ['TZ_FEAT_MCP_DEDUP'] = '1'  # default is set by the main session in tzlib.FEATURES
import tztoolprune as T

ROOT = os.path.join(H, '.claude', 'projects'); n = [0]


def session(proj, used=(), listed=(), prompts=2):
    d = os.path.join(ROOT, proj); os.makedirs(d, exist_ok=True)
    n[0] += 1; p = os.path.join(d, f's{n[0]}.jsonl')
    L = [{'type': 'attachment', 'attachment': {'type': 'deferred_tools_delta', 'addedNames': list(listed), 'removedNames': []}}]
    for i in range(prompts):
        L.append({'type': 'user', 'message': {'role': 'user', 'content': f'prompt {i}'}})
    for t in used:
        L.append({'type': 'assistant', 'message': {'role': 'assistant', 'content': [{'type': 'tool_use', 'id': 'x', 'name': t, 'input': {}}]}})
    open(p, 'w').write('\n'.join(json.dumps(x) for x in L) + '\n')
    os.utime(p, (time.time() + n[0], time.time() + n[0]))   # strictly newer each time
    return p


CAT = ['CronCreate', 'ShareOnboardingGuide', 'Workflow', 'NotebookEdit', 'Read', 'Bash', 'WebFetch', 'mcp__s__get']
for _ in range(3):
    session('p', used=['Read', 'Bash'], listed=CAT, prompts=2)
KW = dict(evidence=5, min_sessions=2, floor=5)           # TE test config: 3 sessions x 2 prompts = 6 prompts >= 5
res = T.analyse(ROOT, **KW); V = {r['tool']: r for r in res['rows']}
prune = sorted(t for t, r in V.items() if r['verdict'] == 'prune')
ok('parity 1: 3 sessions/6 prompts propose exactly the unused ones', prune == ['CronCreate', 'ShareOnboardingGuide', 'Workflow', 'mcp__s__get'])
ok('streak and prompts counted', V['CronCreate']['streak'] == 3 and V['CronCreate']['prompts'] == 6)
ok('parity 3: NotebookEdit high-risk not proposed at 1x', V['NotebookEdit']['verdict'] == 'keep')
ok('protected tools never listed', not {'Read', 'Bash', 'WebFetch'} & set(V))
ok('default thresholds (10 prompts) need more evidence', all(r['verdict'] == 'keep' for r in T.analyse(ROOT)['rows']))
for _ in range(9):
    session('p', used=['Read'], listed=CAT, prompts=2)
res = T.analyse(ROOT, n=12, **KW); V = {r['tool']: r for r in res['rows']}
ok('parity 3: NotebookEdit proposed at 3x streak', V['NotebookEdit']['streak'] == 12 and V['NotebookEdit']['verdict'] == 'prune')
session('p', used=['CronCreate'], listed=CAT)
V = {r['tool']: r for r in T.analyse(ROOT, **KW)['rows']}
ok('parity 2: a used tool resets streak and is not proposed', V['CronCreate']['streak'] == 0 and V['CronCreate']['verdict'] == 'keep')
ok('est cost is chars/4 of the name line', V['Workflow']['chars'] == len('Workflow') + 1)
ok('extra protect glob', 'mcp__s__get' not in {r['tool'] for r in T.analyse(ROOT, protect=('mcp__s__*',), **KW)['rows']})
ok('own tz tools protected', T.protected('mcp__token-zombie__tz_map') and T.protected('ToolSearch'))
ok('report is labelled est and changes nothing', '[est]' in T.report(res) and 'Nothing changed' in T.report(res))

# apply / restore round trip
P = tempfile.mkdtemp(); os.makedirs(os.path.join(P, '.git', 'info')); S = os.path.join(P, '.claude', 'settings.local.json')
os.makedirs(os.path.dirname(S)); orig = json.dumps({'permissions': {'deny': ['WebSearch'], 'allow': ['Bash(ls)']}}, indent=2) + '\n'
open(S, 'w').write(orig)
want = ['Workflow', 'ShareOnboardingGuide', 'Read', 'mcp__token-zombie__tz_map', 'WebSearch']
add = T.apply(S, want, P)
cur = json.load(open(S))
ok('apply adds bare names, user entry kept', cur['permissions']['deny'] == ['WebSearch', 'Workflow', 'ShareOnboardingGuide'])
ok('protected names refused, existing deny not re-added', add == ['Workflow', 'ShareOnboardingGuide'])
ok('allow list untouched', cur['permissions']['allow'] == ['Bash(ls)'])
ok('record + backup + git exclude', os.path.exists(os.path.join(P, '.claude', 'untool_applied.json'))
   and any('.tzbak-' in f for f in os.listdir(os.path.join(P, '.claude'))) and 'untool_applied.json' in open(os.path.join(P, '.git/info/exclude')).read())
ok('restore removes exactly ours, byte-identical (parity 4)', T.restore(S) == ['Workflow', 'ShareOnboardingGuide'] and open(S).read() == orig)
ok('record gone after restore; second restore is a no-op', T.restore(S) == [])
T.apply(S, ['Workflow'], P)
d = json.load(open(S)); d['permissions']['deny'].append('Custom'); open(S, 'w').write(json.dumps(d))
T.restore(S); ok('edited since apply: only our entry removed', json.load(open(S))['permissions']['deny'] == ['WebSearch', 'Custom'])
# no settings file: created then removed again
S2 = os.path.join(tempfile.mkdtemp(), '.claude', 'settings.local.json')
T.apply(S2, ['Workflow']); ok('creates file', json.load(open(S2))['permissions']['deny'] == ['Workflow'])
T.restore(S2); ok('restore removes the file we created', not os.path.exists(S2))
bad = os.path.join(P, '.claude', 'bad.json'); open(bad, 'w').write('{nope')
try:
    T.apply(bad, ['Workflow']); ok('invalid JSON aborts', False)
except RuntimeError:
    ok('invalid JSON aborts, file untouched', open(bad).read() == '{nope')
# CLI: default = report only
S3 = os.path.join(tempfile.mkdtemp(), 's.json')
T.main(['--root', ROOT, '--settings', S3, '--evidence', '5']); ok('no flag writes nothing', not os.path.exists(S3))
T.main(['--root', ROOT, '--settings', S3, '--evidence', '5', '--apply'])
ok('--apply writes', 'ShareOnboardingGuide' in json.load(open(S3))['permissions']['deny'])
T.main(['--settings', S3, '--restore']); ok('--restore empties', not os.path.exists(S3))

# mcp_dup
def tr(calls):
    p = os.path.join(tempfile.mkdtemp(), 't.jsonl'); L = []
    for i, (name, inp, err) in enumerate(calls):
        L.append({'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': f'i{i}', 'name': name, 'input': inp}]}})
        L.append({'type': 'user', 'message': {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': f'i{i}', 'content': 'r', 'is_error': err}]}})
    open(p, 'w').write('\n'.join(json.dumps(x) for x in L) + '\n'); return p
G = 'mcp__x__get'
q = lambda p, t=G, i={'a': 1}: T.mcp_dup({'tool_name': t, 'tool_input': i, 'transcript_path': p})
ok('mcp_dup: identical earlier call -> advice', 'already answered' in q(tr([(G, {'a': 1}, False)])))
ok('mcp_dup: different args -> none', q(tr([(G, {'a': 2}, False)])) == '')
ok('mcp_dup: key order and nulls normalised', q(tr([(G, {'b': None, 'a': 1}, False)])) != '' and q(tr([(G, {'z': 1, 'a': 1}, False)]), i={'a': 1, 'z': 1}) != '')
ok('mcp_dup: earlier error -> none', q(tr([(G, {'a': 1}, True)])) == '')
ok('mcp_dup: Edit in between -> none', q(tr([(G, {'a': 1}, False), ('Edit', {'f': 1}, False)])) == '')
ok('mcp_dup: later repeat after the write counts', q(tr([(G, {'a': 1}, False), ('Edit', {}, False), (G, {'a': 1}, False)])) != '')
ok('mcp_dup: mutating tool never advised', q(tr([('mcp__x__send', {'a': 1}, False)]), 'mcp__x__send') == '')
ok('mcp_dup: non-mcp or no transcript -> none', q(tr([('Read', {'a': 1}, False)]), 'Read') == '' and q('/nope') == '')
os.environ['TZ_FEAT_MCP_DEDUP'] = '1'; ok('mcp_dup works with feature on', q(tr([(G, {'a': 1}, False)])) != '')
os.environ['TZ_FEAT_MCP_DEDUP'] = '0'; ok('mcp_dup off with feature off', q(tr([(G, {'a': 1}, False)])) == '')
done()
