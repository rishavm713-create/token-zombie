#!/bin/bash
# Live ledger (skill states, agent lifecycle, conservative dedupe, hook timing) + hook bench + A/B preflight. Fake HOME, no network, no paid runs.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; mkdir -p "$H/.claude/skills/demo"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
echo -e "---\nname: demo\ndescription: d\n---" > "$H/.claude/skills/demo/SKILL.md"
g() { echo "$1" | HOME="$H" TZ_SUP=0 TZ_DEDUPE=0 python3 "$Z/bin/tz-guard.py"; }
ev() { echo "{\"session_id\":\"s1\",\"cwd\":\"$T\",\"hook_event_name\":\"$1\"${2:+,$2}}"; }
L() { HOME="$H" python3 -c "import json;s=json.load(open('$H/.claude/token-zombie/live-s1.json'));print($1)"; }
GREP='"tool_name":"Grep","tool_input":{"pattern":"foo","path":"."}'
# dedupe: Grep
o=$(g "$(ev PreToolUse "$GREP")"); ok "first Grep: no advice" '[ -z "$o" ]'
g "$(ev PostToolUse "$GREP")" >/dev/null
o=$(g "$(ev PreToolUse "$GREP")"); ok "identical Grep, no file change: advice" '[[ $o == *"identical Grep"* ]]'
ok "advice is never a deny" '[[ $o != *deny* ]]'
ok "advice is valid single JSON" 'echo "$o" | python3 -c "import json,sys;json.load(sys.stdin)"'
o=$(g "$(ev PreToolUse "$GREP")"); ok "same key advised once only (repeat = needed)" '[ -z "$o" ]'
g "$(ev PostToolUse "$GREP")" >/dev/null
g "$(ev PostToolUse '"tool_name":"Edit","tool_input":{"file_path":"x"}')" >/dev/null
o=$(g "$(ev PreToolUse "$GREP")"); ok "after Edit: stale, no advice" '[ -z "$o" ]'
g "$(ev PostToolUse "$GREP")" >/dev/null
g "$(ev PostToolUse '"tool_name":"mcp__x__write","tool_input":{}')" >/dev/null
o=$(g "$(ev PreToolUse "$GREP")"); ok "after unknown MCP tool: stale, no advice" '[ -z "$o" ]'
g "$(ev PostToolUse "$GREP")" >/dev/null
g "$(ev PostToolUse '"tool_name":"Read","tool_input":{"file_path":"x"}')" >/dev/null
o=$(g "$(ev PreToolUse "$GREP")"); ok "after read-only Read: still advised" '[[ $o == *"identical Grep"* ]]'
OTHER='"tool_name":"Grep","tool_input":{"pattern":"foo","path":"src"}'
g "$(ev PostToolUse "$GREP")" >/dev/null; o=$(g "$(ev PreToolUse "$OTHER")"); ok "different args: no advice" '[ -z "$o" ]'
B='"tool_name":"Bash","tool_input":{"command":"ls"}'
for i in 1 2; do g "$(ev PreToolUse "$B")" >/dev/null; g "$(ev PostToolUse "$B")" >/dev/null; done
o=$(g "$(ev PreToolUse "$B")"); ok "Bash never deduped" '[ -z "$o" ]'
g "$(ev PostToolUse "$GREP")" >/dev/null; g "$(ev PreCompact)" >/dev/null
o=$(g "$(ev PreToolUse "$GREP")"); ok "after compaction: nothing is 'still above'" '[ -z "$o" ]'
ok "compaction counted" '[ "$(L "s[\"dedupe\"][\"compactions\"]")" = 1 ]'
W='"tool_name":"WebSearch","tool_input":{"query":"q"}'
g "$(ev PostToolUse "$W")" >/dev/null; o=$(g "$(ev PreToolUse "$W")"); ok "same WebSearch within 30 min: advice" '[[ $o == *"identical WebSearch"* ]]'
# skills: invoked vs loaded vs discovered vs installed/enabled
g "$(ev PostToolUse '"tool_name":"Skill","tool_input":{"skill":"demo"}')" >/dev/null
g "$(ev UserPromptSubmit '"prompt":"/demo now"')" >/dev/null
g "$(ev UserPromptSubmit '"prompt":"/notaskill x"')" >/dev/null
HOME="$H" python3 -c "import sys;sys.path.insert(0,'$Z/bin');import tzlive;tzlive.discovered('s1',['video'])"
ok "invoked = Skill tool only" '[ "$(L "s[\"skills\"][\"invoked\"]")" = "{'"'"'demo'"'"': 1}" ]'
ok "/slash loads, unknown slash ignored" '[ "$(L "sorted(s[\"skills\"][\"loaded\"])")" = "['"'"'demo'"'"']" ]'
ok "discovered kept apart" '[ "$(L "list(s[\"skills\"][\"discovered\"])")" = "['"'"'video'"'"']" ]'
o=$(HOME="$H" python3 "$Z/bin/tz" live skills --session s1 --json)
ok "skills report: installed/enabled/discovered/loaded/invoked" 'echo "$o" | python3 -c "import json,sys;d=json.load(sys.stdin);assert (d[\"installed\"],d[\"enabled\"],d[\"discovered\"],d[\"loaded\"],d[\"invoked\"])==(1,1,1,1,1),d"'
# agents
A='"tool_name":"Agent","tool_use_id":"a1","tool_input":{"subagent_type":"Explore","model":"haiku","run_in_background":true,"description":"scan"}'
g "$(ev PreToolUse "$A")" >/dev/null; ok "agent starting" '[ "$(L "s[\"agents\"][\"a1\"][\"status\"]")" = starting ]'
g "$(ev PostToolUse "$A")" >/dev/null; ok "background agent running after launch" '[ "$(L "s[\"agents\"][\"a1\"][\"status\"]")" = running ]'
ok "agent model recorded" '[ "$(L "s[\"agents\"][\"a1\"][\"model\"]")" = haiku ]'
HOME="$H" python3 -c "
import sys,time;sys.path.insert(0,'$Z/bin');import tzlive
a=tzlive.on_event({'session_id':'s1','hook_event_name':'UserPromptSubmit','prompt':'hi'},now=time.time()+4000)
b=tzlive.on_event({'session_id':'s1','hook_event_name':'UserPromptSubmit','prompt':'hi'},now=time.time()+4000)
assert 'background agent' in a and 'scan' in a and b=='',(a,b)" ; ok "old background agent: one check note, not repeated" '[ $? = 0 ]'
g "$(ev SubagentStop)" >/dev/null; ok "SubagentStop closes the one running agent" '[ "$(L "s[\"agents\"][\"a1\"][\"status\"]")" = done ]'
F='"tool_name":"Agent","tool_use_id":"a2","tool_input":{"description":"x"},"tool_response":{"is_error":true}'
g "$(ev PreToolUse "$F")" >/dev/null; g "$(ev PostToolUse "$F")" >/dev/null; ok "failed agent" '[ "$(L "s[\"agents\"][\"a2\"][\"status\"]")" = failed ]'
g "$(ev SubagentStop)" >/dev/null; ok "unmatched stop counted, not guessed" '[ "$(L "s[\"notes\"].get(\"unmatched_subagent_stops\")")" = 1 ]'
o=$(HOME="$H" python3 "$Z/bin/tz" live agents --session s1); ok "tz live agents lists states" '[[ $o == *"done 1"* && $o == *"failed 1"* ]]'
# hook timing + overhead chars
ok "hook timing recorded per event" '[ "$(L "s[\"hooks\"][\"PreToolUse:Grep\"][\"n\"] > 3 and s[\"hooks\"][\"PreToolUse:Grep\"][\"chars\"] > 0")" = True ]'
# Read deny + pending advice -> still exactly one JSON object
BIG="$T/big.txt"; python3 -c "open('$BIG','w').write('x'*400000)"
RD="\"tool_name\":\"Read\",\"tool_input\":{\"file_path\":\"$BIG\"}"
o=$(g "$(ev PreToolUse "$RD")"); ok "big Read: one JSON object" '[ "$(echo "$o" | grep -c hookSpecificOutput)" = 1 ]'
# base cache: first-reply size stored once per session
TR="$T/chat.jsonl"; for n in 1 2; do echo "{\"type\":\"assistant\",\"message\":{\"id\":\"m$n\",\"usage\":{\"input_tokens\":1,\"output_tokens\":1,\"cache_read_input_tokens\":$((n*50000)),\"cache_creation_input_tokens\":0}}}" >> "$TR"; done
g "{\"session_id\":\"s2\",\"hook_event_name\":\"PostToolUse\",\"tool_name\":\"Bash\",\"transcript_path\":\"$TR\"}" >/dev/null
ok "first-reply size cached" '[ "$(cat "$H/.claude/token-zombie/base-s2")" = 50001 ]'
o=$(g '{garbage'); ok "guard survives bad input" '[ $? = 0 ]'
# hook bench
o=$(HOME="$H" python3 "$Z/bin/tz" hooks bench --mb 0.2 --n 2); ok "hooks bench prints MEASURED rows" '[[ $o == *MEASURED* && $o == *PostToolUse* ]]'
# preflight validate: one valid arm, one invalid
E="$T/ev"; mkdir -p "$E/work/A-t" "$E/work/B-t"
for a in A-t B-t; do git -C "$E/work/$a" init -q; echo a > "$E/work/$a/f"; git -C "$E/work/$a" add -A; git -C "$E/work/$a" -c user.email=a@a -c user.name=a commit -qm s; done
echo b >> "$E/work/A-t/f"
for a in A-t B-t; do echo '{"status":"ok","total":1}' > "$E/$a.result.json"; done
echo '{"type":"result","is_error":false,"permission_denials":[]}' > "$E/A-t.stream.jsonl"
echo '{"type":"result","is_error":false,"permission_denials":[{"tool_name":"Edit"}]}' > "$E/B-t.stream.jsonl"
o=$(python3 "$Z/bin/tz" preflight --validate "$E"); ok "validate: invalid arm -> run INVALID" '[ $? = 1 ] && [[ $o == *"A-t      VALID"* && $o == *"B-t      INVALID"* && $o == *"run INVALID"* ]]'
echo '{"type":"result","is_error":false,"permission_denials":[]}' > "$E/B-t.stream.jsonl"
o=$(python3 "$Z/bin/tz" preflight --validate "$E"); ok "validate: B has 0 files changed -> still INVALID" '[[ $o == *"run INVALID"* ]]'
echo c >> "$E/work/B-t/f"; o=$(python3 "$Z/bin/tz" preflight --validate "$E"); ok "validate: all arms ok -> VALID" '[[ $o == *"run VALID"* ]]'
# preflight smoke: refuses without --yes (S1-S4 with a fake CLI: tests/test_smoke.sh)
o=$(python3 "$Z/bin/tz" preflight --smoke --evidence "$T/ev2"); ok "smoke without --yes: not run, not ready" '[[ $o == *"not run: spends real tokens"* && $o == *"NOT READY"* ]]'
# trimmed output (tzout) is not "still above": guard sets calls[key].trimmed, tzlive's fresh test skips it
GP=$(python3 -c "import json;print(json.dumps({'hook_event_name':'PostToolUse','session_id':'trim1','cwd':'/t','tool_name':'Grep','tool_input':{'pattern':'Q'},'tool_response':{'mode':'content','content':'qqqq\\n'*5000}}))")
g "$GP" >/dev/null; o=$(g "${GP/PostToolUse/PreToolUse}")
ok "trimmed Grep: no 'still above' note" '[[ $o != *"still above"* ]]'
GP2="${GP/trim1/trim2}"; echo "$GP2" | HOME="$H" TZ_SUP=0 TZ_OUT=0 python3 "$Z/bin/tz-guard.py" >/dev/null; o=$(g "${GP2/PostToolUse/PreToolUse}")
ok "untrimmed Grep: 'still above' note kept" '[[ $o == *"still above"* ]]'
# SubagentStart/Stop by agent_id, InstructionsLoaded, PostCompact (registered hooks, exact data)
for J in '{"hook_event_name":"SubagentStart","session_id":"hk1","agent_id":"a1","agent_type":"Explore"}' '{"hook_event_name":"SubagentStart","session_id":"hk1","agent_id":"a2","agent_type":"Plan"}' '{"hook_event_name":"SubagentStop","session_id":"hk1","agent_id":"a1"}' '{"hook_event_name":"InstructionsLoaded","session_id":"hk1","file_path":"'"$Z"'/README.md","load_reason":"session_start"}' '{"hook_event_name":"PostCompact","session_id":"hk1","trigger":"auto"}'; do g "$J" >/dev/null; done
o=$(HOME="$H" python3 -c "import json;s=json.load(open('$H/.claude/token-zombie/live-hk1.json'));print(s['agents']['a1']['status'],s['agents']['a2']['status'],len(s['instr']),len(s['compact']),s['notes'].get('unmatched_subagent_stops',0))")
ok "hooks: agent_id exact stop (a1 done, a2 running), 1 instr file, 1 compaction, 0 unmatched" '[[ $o == "done running 1 1 0" ]]'
AG='{"hook_event_name":"PreToolUse","session_id":"dd1","tool_name":"Agent","tool_use_id":"t1","tool_input":{"subagent_type":"Explore","description":"Find auth code"}}'
g "$AG" >/dev/null; o=$(g "${AG/t1/t2}")
ok "duplicate agent assignment: advice on 2nd identical, none on 1st" '[[ $o == *"same type and description"* ]]'
o=$(g "${AG/dd1/dd2}"); ok "first agent in a chat: no duplicate advice" '[[ $o != *"same type and description"* ]]'
# agent ROI (cost per agent_id from subagent transcripts) + compaction verification
RS=roi1; mkdir -p "$H/.claude/projects/p/$RS/subagents"
printf '%s\n' '{"message":{"id":"m1","model":"claude-sonnet-4-5","usage":{"input_tokens":100,"output_tokens":50},"content":[{"type":"text","text":"done"}]}}' > "$H/.claude/projects/p/$RS/subagents/agent-r1.jsonl"
for J in '{"hook_event_name":"SubagentStart","session_id":"roi1","agent_id":"r1","agent_type":"Explore"}' '{"hook_event_name":"SubagentStop","session_id":"roi1","agent_id":"r1"}'; do g "$J" >/dev/null; done
o=$(HOME="$H" python3 "$Z/bin/tz" live roi --session roi1); ok "agent ROI: cost joined by agent_id, small spawn flagged" '[[ $o == *"1 agents"* && $o == *"calls 1"* && $o == *small* ]]'
printf '# Continuation x\nChanged files (git, uncommitted): bin/tzlive.py, bin/tzout.py\nOwner last asked: verify compaction summaries\n' > "$H/.claude/token-zombie/compact-cv1.md"
g '{"hook_event_name":"PostCompact","session_id":"cv1","trigger":"auto","compact_summary":"unrelated text"}' >/dev/null
o=$(g '{"hook_event_name":"UserPromptSubmit","session_id":"cv1","prompt":"go"}'); ok "weak compaction summary: one advice naming the note" '[[ $o == *"compaction summary kept only"* && $o == *compact-cv1.md* ]]'
o=$(g '{"hook_event_name":"UserPromptSubmit","session_id":"cv1","prompt":"go"}'); ok "compaction advice only once" '[[ $o != *"compaction summary kept only"* ]]'
g '{"hook_event_name":"PostCompact","session_id":"cv2","trigger":"auto"}' >/dev/null
ok "no summary text: verdict unknown, never guessed" '[ "$(HOME="$H" python3 -c "import json;print(json.load(open(\"$H/.claude/token-zombie/live-cv2.json\"))[\"compact\"][-1][\"verdict\"])")" = unknown ]'
for J in '{"hook_event_name":"PostToolBatch","session_id":"ev1"}' '{"hook_event_name":"PreModelSwitch","session_id":"ev1","model":"opus"}' '{"hook_event_name":"PostModelSwitch","session_id":"ev1","model":"sonnet"}' '{"hook_event_name":"WorktreeCreate","session_id":"ev1","worktree_path":"/w/a"}' '{"hook_event_name":"WorktreeRemove","session_id":"ev1","worktree_path":"/w/a"}'; do g "$J" >/dev/null; done
o=$(HOME="$H" python3 -c "import json;s=json.load(open('$H/.claude/token-zombie/live-ev1.json'));print(s['events']['tool_batches'],[m['model'] for m in s['models']],s['worktrees']['/w/a']['state'])")
ok "batch/model-switch/worktree events recorded" '[[ $o == "1 ['"'"'opus'"'"', '"'"'sonnet'"'"'] removed" ]]'
mkdir -p "$H/.claude/projects/p/st1/subagents"; echo '{"message":{"id":"m","model":"claude-sonnet-4-5","usage":{"input_tokens":5,"output_tokens":5}}}' > "$H/.claude/projects/p/st1/subagents/agent-q1.jsonl"; touch -t 202001010000 "$H/.claude/projects/p/st1/subagents/agent-q1.jsonl"
g '{"hook_event_name":"SubagentStart","session_id":"st1","agent_id":"q1","agent_type":"Explore"}' >/dev/null
o=$(HOME="$H" python3 "$Z/bin/tz" live roi --session st1); ok "stalled agent flagged (running, transcript quiet)" '[[ $o == *stalled* ]]'
rm -rf "$T"; echo "live: pass $pass fail $fail"; [ $fail = 0 ]
