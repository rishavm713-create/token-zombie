# tzline (ccstatusline port): render with a layout, ccstatusline settings import, no crash on bad input.
import json, os, tempfile
os.environ['HOME'] = tempfile.mkdtemp()
for k in [k for k in os.environ if k.startswith('TZ_')]:
    del os.environ[k]
from harness import ok, done
import tzline as L
import time
now = time.time()
d = L.sample(now)
ok('sample has model', d['model']['display_name'])
out = L.render(d, '', '', {'lines': [[{'id': 'a', 'type': 'model'}]]}, now)
ok('model widget renders', 'Sonnet' in out)
ok('empty layout renders nothing', L.render(d, '', '', {'lines': [[]]}, now) == '')
ok('non-list line ignored', L.render(d, '', '', {'lines': ['x']}, now) == '')
ok('host mode resets colour', L.render(d, '', '', {'lines': [[{'id': 'a', 'type': 'model'}]]}, now, host=True).startswith('\x1b[0m'))
f = os.path.join(tempfile.mkdtemp(), 's.json')
json.dump({'lines': [[{'id': '1', 'type': 'model'}, {'id': '2', 'type': 'no-such-widget'}]], 'globalBold': True}, open(f, 'w'))
lay, unknown = L.import_config(f)
ok('import keeps lines/version', lay['version'] == 3 and lay['globalBold'] is True and len(lay['lines'][0]) == 2)
ok('import reports unsupported widget', unknown == ['no-such-widget'])
bad = os.path.join(tempfile.mkdtemp(), 'b.json'); open(bad, 'w').write('[]')
try:
    L.import_config(bad); raised = False
except ValueError:
    raised = True
ok('import rejects non-settings file', raised)
done()
