#!/bin/bash
# Full v0.1 suite: sums real pass/fail counts of every test script. Run: bash tests/run_all.sh
export TZ_DEDUPE=0  # existing tests replay identical payloads on purpose; dedupe has its own test (test_dedupe)
R="$(cd "$(dirname "$0")/.." && pwd)"; DOCS="docs/BUILD-LOG.md docs/DEVELOPMENT-STATE.md docs/HANDOFF.md docs/NEXT-SESSION.md"
CLEAN=""; for f in $DOCS; do git -C "$R" diff --quiet -- "$f" 2>/dev/null && CLEAN="$CLEAN $f"; done  # tests rewrite these; restore the ones that were clean
# Git Bash on Windows: pwd gives /d/a/..., which Windows Python cannot open; use D:/a/... (works in both)
# MSYS also rewrites an inherited TMPDIR back to /d/... when bash starts, so mktemp paths must be converted here too.
# PYTHONUTF8: same as bin/tzpy (Windows Python would otherwise read/write cp1252).
case "$(uname -s)" in MINGW*|MSYS*) pwd() { builtin pwd -W; }; export -f pwd; export TMPDIR="$(cygpath -m "${TMPDIR:-/tmp}")" PYTHONUTF8=1;; esac
D="$(cd "$(dirname "$0")" && pwd)"; P=0; F=0; S=0
for t in test_benchplan test_memwin test_oss_wins test_tz test_continuity test_usage test_opt test_cap test_cli test_install test_bench test_auto test_ab test_sup test_e2e test_install2 test_hard test_status_read test_modes test_plugin test_host test_dash2 test_repo test_live test_out test_vet test_smoke test_next test_cont test_ondemand test_rework test_hooklive test_gaps test_jsskel test_price test_attr test_codex test_policy test_dedupe test_replay test_split test_cost test_agent test_upgrade test_gate2 test_worktree_own test_repo_intel test_gaps_p1 test_rollback test_killgroup test_v21; do
  [ -f "$D/$t.sh" ] || continue
  TO=""; command -v timeout >/dev/null && TO="timeout ${TZ_SUITE_TIMEOUT:-600}"
  out=$($TO bash "$D/$t.sh" 2>&1); rc=$?; [ $rc = 124 ] && out="$out
FAIL: $t timed out after ${TZ_SUITE_TIMEOUT:-600}s (hang)
pass 0 fail 1"; echo "$out" | grep -E '^(FAIL|SKIP)' ; S=$((S+$(echo "$out" | grep -c '^SKIP'))); line=$(echo "$out" | grep -E 'pass[ :]+[0-9]+' | tail -1)
  p=$(echo "$line" | sed -E 's/.*pass[ :]+([0-9]+).*/\1/'); f=$(echo "$line" | sed -E 's/.*fail[ :]+([0-9]+).*/\1/')
  echo "$t: $line"; P=$((P+${p:-0})); F=$((F+${f:-0}))
  [ -n "$TZ_SUITE_VERBOSE" ] && [ "${f:-0}" != 0 ] && echo "$out" | tail -${TZ_SUITE_VERBOSE_LINES:-60} | sed "s/^/  | $t | /"  # CI diagnostics: context of a failing file
done
[ -n "$CLEAN" ] && git -C "$R" checkout -- $CLEAN 2>/dev/null
echo "TOTAL pass $P fail $F skip $S (skips are not counted as passes)"; [ $F = 0 ]
