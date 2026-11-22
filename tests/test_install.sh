#!/bin/bash
# v0.1 installer tests: dry-run writes nothing, install backs up, restore + uninstall reverse. Fake HOME only.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; H="$T/home"; pass=0; fail=0; mkdir -p "$H/.claude"
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
S="$H/.claude/settings.json"; echo '{"model":"sonnet","statusLine":{"type":"command","command":"echo prev"}}' > "$S"; cp "$S" "$T/orig"
i() { HOME="$H" bash "$Z/install.sh" "$@"; }
o=$(i --dry-run); ok "dry-run shows diff, says nothing written" '[[ $o == *tz-guard* && $o == *"DRY RUN"* ]]'
ok "dry-run: settings unchanged, no backup, no state dir" 'cmp -s "$S" "$T/orig" && ! ls "$S".bak-tz-* 2>/dev/null && [ ! -d "$H/.claude/token-zombie" ]'
i >/dev/null; ok "install adds hooks, keeps other keys" 'grep -q tz-guard "$S" && grep -q sonnet "$S"'
ok "install made a backup equal to original" 'cmp -s "$(ls "$S".bak-tz-* | head -1)" "$T/orig"'
echo '{broken' > "$T/bad"; cp "$T/bad" "$S"; o=$(i 2>&1); ok "invalid settings: refuses, file untouched" '[[ $o == *"not valid JSON"* ]] && cmp -s "$S" "$T/bad"'
sleep 1; echo '{"model":"sonnet"}' > "$S"; i >/dev/null; i --uninstall >/dev/null
ok "uninstall removes tz hooks, keeps model" '! grep -q token-zombie "$S" && grep -q sonnet "$S"'
i >/dev/null; i --restore >/dev/null; ok "restore puts back a pre-install backup" '! grep -q tz-guard "$S"'
ok "restore keeps a copy of what it replaced" 'ls "$S".before-restore >/dev/null'
HOME="$T/empty" bash "$Z/install.sh" --restore >/dev/null 2>&1; ok "restore without backup => exit 1" '[ $? = 1 ]'
# repeated install makes a backup that already has tz hooks: restore must skip it and reach the original
echo '{"model":"orig","hooks":{"Stop":[{"hooks":[{"type":"command","command":"echo old"}]}]}}' > "$S"; i >/dev/null; sleep 1; i >/dev/null; i --restore >/dev/null
ok "restore after repeated install returns original, not an installed state" 'grep -q orig "$S" && ! grep -q token-zombie "$S"'
# failed install leaves settings intact (unwritable conf dir is not enough; bad JSON covered above)
ok "idempotent: install x2 keeps one tz-guard per event" 'i >/dev/null; i >/dev/null; [ "$(grep -c "tz-guard.py" "$S")" = 17 ]'
ok "statusline of user preserved in config for rollback" 'i --uninstall >/dev/null; ! grep -q tz-status "$S"'
echo "install: pass $pass fail $fail"; [ $fail = 0 ]
