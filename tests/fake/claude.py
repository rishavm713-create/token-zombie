#!/usr/bin/env python3
# Offline fake `claude -p` for the smoke tests. It plays the host: runs the PostToolUse hook from --settings with the
# scenario's tool result (so tzout really trims and spills to the recall store), then prints stream-json.
# FAKE_MODE: good | bash (uses Bash in S2) | leak (S4 quotes the middle code word) | noid (S2 omits the id) |
#            deny (S1 permission denial) | touchlive (writes the file in FAKE_LIVE) | big (reports 300k tokens per call) | crash (S3 exits 1)
import json, os, re, subprocess, sys, shutil
a = sys.argv[1:]; prompt = a[a.index('-p') + 1]; mode = os.environ.get('FAKE_MODE', 'good')
opt = lambda k: a[a.index(k) + 1] if k in a else None
n = [0]
def say(content, tok=100):
    n[0] += 1
    print(json.dumps({'type': 'assistant', 'message': {'id': f'm{n[0]}', 'content': content, 'usage': {'input_tokens': tok, 'output_tokens': 1,
          'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0}}}), flush=True)
def done(text, denials=()):
    print(json.dumps({'type': 'result', 'is_error': False, 'result': text, 'permission_denials': list(denials)}), flush=True)
def hook(tool, ti, resp):
    cmd = json.load(open(opt('--settings')))['hooks']['PostToolUse'][0]['hooks'][0]['command']
    pl = dict(hook_event_name='PostToolUse', session_id='fake', cwd=os.getcwd(), tool_name=tool, tool_input=ti, tool_response=resp)
    # Claude Code runs hook commands in Git Bash on Windows, not cmd.exe
    argv = [shutil.which('bash') or 'bash', '-c', cmd] if os.name == 'nt' else cmd
    out = subprocess.run(argv, shell=os.name != 'nt', input=json.dumps(pl), capture_output=True, text=True).stdout
    m = re.search(r'tz recall ([0-9a-f]{10})', out)
    return m.group(1) if m else 'NONE'
tok = 300_000 if mode == 'big' else 100
if mode == 'touchlive':
    open(os.environ['FAKE_LIVE'], 'a').write('x')
if 'calc.py' in prompt:
    if mode == 'deny':
        say([]); done('denied', [{'tool_name': 'Edit'}]); sys.exit(0)
    s = open('calc.py').read().replace('a - b', 'a + b'); open('calc.py', 'w').write(s)
    subprocess.run([sys.executable, '-m', 'unittest', '-q'], capture_output=True)
    say([{'type': 'tool_use', 'name': 'Bash', 'input': {'command': 'python3 -m unittest -q'}}], tok); done('fixed')
elif 'big.txt' in prompt:
    p = os.path.abspath('big.txt'); c = open(p).read()
    rid = hook('Read', {'file_path': p}, {'type': 'text', 'file': {'filePath': p, 'content': c, 'numLines': c.count('\n'), 'startLine': 1, 'totalLines': c.count('\n')}})
    say([{'type': 'tool_use', 'name': 'Bash' if mode == 'bash' else 'Read', 'input': {'file_path': p}}], tok)
    done('NONE' if mode == 'noid' else rid)
elif 'WebFetch' in prompt:
    if mode == 'crash':
        sys.exit(1)
    rid = hook('WebFetch', {'url': 'https://x', 'prompt': 'p'}, {'result': 'w' * 3000, 'url': 'https://x', 'code': 200})
    say([{'type': 'tool_use', 'name': 'WebFetch', 'input': {'url': 'https://x'}}], tok); done(rid)
elif 'bigtext' in prompt:
    mc = json.load(open(opt('--mcp-config')))['mcpServers']['tzsmoke']
    txt = subprocess.run([mc['command'], *mc['args']], input='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"bigtext"}}\n',
                         capture_output=True, text=True, env=dict(os.environ, **mc['env'])).stdout
    blocks = json.loads(txt)['result']['content']
    rid = hook('mcp__tzsmoke__bigtext', {}, blocks)
    say([{'type': 'tool_use', 'name': 'mcp__tzsmoke__bigtext', 'input': {}}], tok)
    done(rid + (' MIDDLE-CODEWORD-' + mc['env']['TZ_SMOKE_SALT'] if mode == 'leak' else ' NOCODE'))
