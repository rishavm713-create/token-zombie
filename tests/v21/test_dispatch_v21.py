# every v2.1 module is reachable through `tz <command>` (exit 0 or a usage line, never "unknown command")
import os, subprocess, sys
from harness import ok, done, Z
CMDS = 'budget ccusage claim stale clihelp debt diag facts fast gitguard line memsearch obs sandbox scrub sg spec squad tbench team trace ts depth impact condense'.split()
for c in CMDS:
    r = subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tz'), c], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
    ok('tz ' + c + ' reachable', 'unknown command' not in (r.stdout + r.stderr) and 'Traceback' not in r.stderr)
r = subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tz'), 'sym', 'A/b'], capture_output=True, text=True, stdin=subprocess.DEVNULL, cwd=Z)
ok('tz sym A/b goes to tzsym (name path)', 'Traceback' not in r.stderr and 'unknown' not in r.stderr)
r = subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tz'), 'sym', 'main'], capture_output=True, text=True, stdin=subprocess.DEVNULL, cwd=Z)
ok('tz sym main still works (tzmap)', 'Traceback' not in r.stderr)
done()
