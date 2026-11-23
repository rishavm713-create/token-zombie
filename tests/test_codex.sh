#!/bin/bash
# Codex adapter usage parser: synthetic rollout logs in a temp HOME (never the real one).
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
tz() { HOME="$H" CODEX_HOME= "$Z/bin/tz" "$@"; }
S="$H/.codex/sessions/2026/11/23"
tc() { echo "{\"type\":\"event_msg\",\"payload\":{\"type\":\"token_count\",\"info\":{\"total_token_usage\":{\"input_tokens\":$1,\"cached_input_tokens\":$2,\"output_tokens\":$3,\"reasoning_output_tokens\":$4,\"total_tokens\":$(($1+$3))}}}}"; }
mkdir -p "$S"
# missing dir
o=$(tz adapters --usage codex --json); ok "missing dir => zero sessions" '[[ $o == *"\"session_count\": 0"* ]]'
# session A: cumulative 100 -> 300 -> 600 input; last wins; null info + malformed line skipped
{ echo '{"type":"session_meta","payload":{"id":"a"}}'; echo '{"type":"turn_context","payload":{"model":"gpt-x"}}'
  tc 100 10 20 5; echo 'not json {'; echo '{"type":"event_msg","payload":{"type":"token_count","info":null}}'; tc 300 30 50 10; tc 600 60 90 20; } > "$S/rollout-a.jsonl"
# session B
{ echo '{"type":"turn_context","payload":{"model":"gpt-y"}}'; tc 1000 0 100 0; } > "$S/rollout-b.jsonl"
# session C old (40 days)
{ tc 5000 0 500 0; } > "$S/rollout-c.jsonl"; touch -t 202510010000 "$S/rollout-c.jsonl"
o=$(tz adapters --usage codex --json)
ok "2 recent sessions (days filter)" '[[ $o == *"\"session_count\": 2"* ]]'
P() { python3 -c "import json,sys;d=json.loads(sys.argv[1]);print($1)" "$o"; }
ok "cumulative: last total per session, summed across sessions" '[ "$(P "d[\"total\"][\"input_tokens\"]")" = 1600 ]'
ok "output + reasoning totals" '[ "$(P "d[\"total\"][\"output_tokens\"]")" = 190 ] && [ "$(P "d[\"total\"][\"reasoning_output_tokens\"]")" = 20 ]'
ok "total_tokens" '[ "$(P "d[\"total\"][\"total_tokens\"]")" = 1790 ]'
ok "models per session" '[[ $o == *"\"model\": \"gpt-x\""* && $o == *"\"model\": \"gpt-y\""* ]]'
ok "marked MEASURED" '[[ $o == *MEASURED* ]]'
o=$(tz adapters --usage codex --days 3650 --json); ok "wide days includes old session" '[[ $o == *"\"session_count\": 3"* ]]'
o=$(tz adapters --usage codex --days 1); ok "text output" '[[ $o == *"2 sessions"* && $o == *"total 1790"* ]]'
# CODEX_HOME override
mkdir -p "$T/ch/sessions/2026/11/23"; tc 7 0 3 0 > "$T/ch/sessions/2026/11/23/rollout-z.jsonl"
o=$(HOME="$H" CODEX_HOME="$T/ch" "$Z/bin/tz" adapters --usage codex --json); ok "CODEX_HOME override" '[[ $o == *"\"session_count\": 1"* && $o == *"\"total_tokens\": 10"* ]]'
ok "unknown agent usage rejected" '! tz adapters --usage cursor >/dev/null 2>&1'
ok "status REAL + usage capability" 'o=$(tz adapters --json); [[ $o == *"\"usage\": true"* ]]'
ok "installed_here via sessions dir" 'python3 -c "import sys,os;os.environ[\"HOME\"]=sys.argv[1];os.environ.pop(\"CODEX_HOME\",None);sys.path.insert(0,sys.argv[2]+\"/bin\");from adapters import codex;sys.exit(0 if codex.installed_here() else 1)" "$H" "$Z"'
rm -rf "$T"
echo "pass $pass fail $fail"; [ $fail = 0 ]
