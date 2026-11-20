#!/bin/bash
# DO NOT RUN WITHOUT APPROVAL: spends real tokens. 4 headless sessions (+1 fresh B2 session). Caps: 1.5M per session, 5M total (bin/tzab.py kills at the cap).
# Usage: bash run_experiment.sh <evidence_dir>   (CLAUDE_CONFIG_DIR is the isolated, user-authenticated set via TZ_AB_CONFIG; live ~/.claude is never used)
set -u
Z="$(cd "$(dirname "$0")/../.." && pwd)"; AB="$Z/tests/ab"; EV="${1:?evidence dir}"; CFG="${TZ_AB_CONFIG:?set TZ_AB_CONFIG to an isolated, logged-in CLAUDE_CONFIG_DIR}"; ST="${TZ_AB_STATE:?set TZ_AB_STATE to a scratch HOME dir for the B-run state}"
run() { python3 "$Z/bin/tzab.py" --name "$1" --cwd "$2" --config "$CFG" --prompt-file "$3" --evidence "$EV" "${@:4}"; }
fresh() { rm -rf "$1"; mkdir -p "$(dirname "$1")"; cp -R "$AB/fixture" "$1"; git -C "$1" init -q; git -C "$1" add -A; git -C "$1" -c user.email=a@a -c user.name=ab commit -qm snapshot; }
# B settings: hooks only for B, state redirected to $ST so the real ~/.claude/token-zombie is untouched
BS="$EV/b-settings.json"; python3 - "$Z" "$ST" "$BS" <<'PY'
import json,sys
z,st,out=sys.argv[1:4]; c=lambda s: f'HOME={st} python3 "{z}/bin/{s}"'
# B hooks = the plugin's own hooks/hooks.json (same events + matchers), state redirected: tz preflight checks parity
d=json.load(open(f'{z}/hooks/hooks.json'))['hooks']
for gs in d.values():
    for g in gs:
        for x in g['hooks']: x['command']=f'HOME={st} '+x['command'].replace('${CLAUDE_PLUGIN_ROOT}',z)
json.dump({'hooks':d},open(out,'w'),indent=1)
PY
mkdir -p "$ST/.claude" "$EV"
W="$EV/work"; rm -rf "$W"
# Task 1
fresh "$W/A-task1"; run A-task1 "$W/A-task1" "$AB/task1.prompt" || exit 3
fresh "$W/B-task1"; run B-task1 "$W/B-task1" "$AB/task1.prompt" --extra-settings "$BS" || exit 3
# Task 2: A = same-session continuation (--resume), B = tz handoff then FRESH session + tz resume
fresh "$W/A-task2"; run A-task2p1 "$W/A-task2" "$AB/task2a.prompt" || exit 3
SID=$(python3 -c "import json,sys;print(next(json.loads(l)['session_id'] for l in open('$EV/A-task2p1.stream.jsonl') if '\"session_id\"' in l))")
run A-task2p2 "$W/A-task2" "$AB/task2b.prompt" --resume "$SID" || exit 3
fresh "$W/B-task2"; { cat "$AB/task2a.prompt"; echo "Then run: python3 $Z/bin/tz handoff --cwd $W/B-task2 --task csv-export --next 'wire --format into cli.py + cli test' --yes"; } > "$EV/b-task2a.prompt"
run B-task2p1 "$W/B-task2" "$EV/b-task2a.prompt" --extra-settings "$BS" || exit 3
{ echo "Start by running: python3 $Z/bin/tz resume --cwd $W/B-task2"; cat "$AB/task2b.prompt"; } > "$EV/b-task2b.prompt"
run B-task2p2 "$W/B-task2" "$EV/b-task2b.prompt" --extra-settings "$BS" || exit 3
for t in A-task1 B-task1; do bash "$AB/accept/accept_task1.sh" "$W/$t" | tail -1; python3 "$AB/score.py" "$AB/fixture" "$W/$t" task1; done
for t in A-task2 B-task2; do bash "$AB/accept/accept_task2.sh" "$W/$t" | tail -1; python3 "$AB/score.py" "$AB/fixture" "$W/$t" task2; done
