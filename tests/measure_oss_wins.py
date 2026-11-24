#!/usr/bin/env python3
"""Before/after on REAL local chat logs (~/.claude/projects/**/*.jsonl). No model calls. Prints MEASURED chars (tokens EST = chars/4).
 re-read stub: Read results >=2000 chars whose (file, bytes) were already returned earlier in the same chat file (compaction not modelled: upper bound).
 crush: tool results >12000 chars, old tzcrush (git HEAD) vs working tree."""
import glob, hashlib, importlib.util, json, os, subprocess, sys
B = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bin')
def load(name, src):
    s = importlib.util.spec_from_loader(name, loader=None); m = importlib.util.module_from_spec(s); exec(src, m.__dict__); return m
sys.path.insert(0, B)
new = load('crush_new', open(os.path.join(B, 'tzcrush.py')).read())
old = load('crush_old', subprocess.run(['git', 'show', 'HEAD:bin/tzcrush.py'], capture_output=True, text=True, cwd=B).stdout)
rr = dict(n=0, saved=0, reads=0); cr = dict(n=0, old=0, new=0, total=0)
for f in glob.glob(os.path.expanduser('~/.claude/projects/**/*.jsonl'), recursive=True):
    names, seen = {}, set()
    try:
        for ln in open(f, errors='replace'):
            try: e = json.loads(ln)
            except ValueError: continue
            c = (e.get('message') or {}).get('content')
            if not isinstance(c, list): continue
            for b in c:
                if not isinstance(b, dict): continue
                if b.get('type') == 'tool_use': names[b.get('id')] = (b.get('name'), b.get('input') or {})
                elif b.get('type') == 'tool_result':
                    nm, ti = names.get(b.get('tool_use_id'), ('', {}))
                    txt = b.get('content'); txt = ''.join(x.get('text', '') for x in txt if isinstance(x, dict)) if isinstance(txt, list) else txt
                    if not isinstance(txt, str): continue
                    if nm == 'Read' and not ti.get('offset') and not ti.get('limit') and len(txt) >= 2000:
                        rr['reads'] += 1; k = (ti.get('file_path'), hashlib.sha1(txt.encode()).hexdigest())
                        if k in seen: rr['n'] += 1; rr['saved'] += len(txt) - 200
                        seen.add(k)
                    elif nm in ('Bash', 'Grep', 'WebFetch') or nm.startswith('mcp__'):
                        if len(txt) > 12000:
                            cr['n'] += 1; cr['total'] += len(txt)
                            for tag, m in (('old', old), ('new', new)):
                                r, _ = m.crush(txt); cr[tag] += len(r) if r else len(txt)
    except OSError: pass
print(f"re-read stub [MEASURED, upper bound, no compaction model]: {rr['n']} of {rr['reads']} full Reads were byte-identical repeats; ~{rr['saved']} chars (~{rr['saved']//4} tok EST) removable")
if cr['n']: print(f"crush [MEASURED]: {cr['n']} results >12k chars, {cr['total']} chars; after old crush {cr['old']}, after new {cr['new']} (extra {cr['old']-cr['new']} chars = ~{(cr['old']-cr['new'])//4} tok EST)")
else: print('crush: no >12k results found')
