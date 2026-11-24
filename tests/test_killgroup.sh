#!/usr/bin/env bash
# worker timeout kills the whole process group (no leaked grandchildren)
cd "$(dirname "$0")/.." || exit 1
R=$PWD; T=$(mktemp -d); P=0; F=0
ok(){ if eval "$1"; then echo "ok $2"; P=$((P+1)); else echo "FAIL $2"; F=$((F+1)); fi; }
cat > "$T/w.sh" <<S
#!/bin/sh
sleep 300 &
echo \$! > $T/child.pid
sleep 300
S
chmod +x "$T/w.sh"
python3 -c "
import sys,subprocess;sys.path.insert(0,'$R/bin');import tzworkers as w
try: w.run_pg(['$T/w.sh'],None,1.5); print('NO')
except subprocess.TimeoutExpired: print('TIMEOUT')" > "$T/o"
ok "grep -q TIMEOUT $T/o" timeout-raised
sleep 0.5
ok "! kill -0 \$(cat $T/child.pid) 2>/dev/null" grandchild-killed
ok "python3 -c \"import sys;sys.path.insert(0,'$R/bin');import tzworkers as w;r=w.run_pg(['echo','hi'],None,5);assert r.stdout.strip()=='hi' and r.returncode==0\"" normal-run
echo "pass $P fail $F"; [ $F = 0 ]
