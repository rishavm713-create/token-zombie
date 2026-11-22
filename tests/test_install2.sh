#!/bin/bash
# Installer hardening: fresh/re-/upgrade/uninstall/restore, foreign hook + statusline preservation, missing/malformed config, crash, failure rollback, idempotence.
Z="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; pass=0; fail=0
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
new() { H="$T/h$1"; mkdir -p "$H/.claude"; S="$H/.claude/settings.json"; C="$H/.claude/token-zombie/config.json"; }
i() { HOME="$H" bash "$Z/install.sh" "$@" 2>&1; }
jq_() { python3 -c "import json,sys;s=json.load(open('$S'));print(eval(sys.argv[1]))" "$1"; }
FOREIGN='{"hooks":{"Stop":[{"hooks":[{"type":"command","command":"echo mine"}]}],"UserPromptSubmit":[{"hooks":[{"type":"command","command":"echo keep"},{"type":"command","command":"python3 /x/token-zombie/bin/tz-guard.py"}]}]},"statusLine":{"type":"command","command":"echo MYSTATUS"},"model":"opus","permissions":{"allow":["Bash(ls)"]}}'
# 1 fresh, no settings file at all
new 1; o=$(i); ok "fresh install, missing settings.json + missing config" '[ -f "$S" ] && [[ $o == *installed* ]] && [ "$(jq_ "len(s[\"hooks\"])")" = 18 ]'
o=$(i --check); ok "--check lists 7 events + tz statusline" '[[ $o == *Stop* && $o == *SessionEnd* && $o == *"statusline: tz"* ]]'
# 2 foreign preserved
new 2; echo "$FOREIGN" >"$S"; i >/dev/null
ok "foreign Stop hook kept" '[ "$(jq_ "sum(1 for g in s[\"hooks\"][\"Stop\"] for x in g[\"hooks\"] if x[\"command\"]==\"echo mine\")")" = 1 ]'
ok "foreign hook in same group as old tz hook kept, old tz hook replaced" '[ "$(jq_ "sum(1 for g in s[\"hooks\"][\"UserPromptSubmit\"] for x in g[\"hooks\"] if \"echo keep\" in x[\"command\"])")" = 1 ] && ! grep -q "/x/token-zombie" "$S"'
ok "unrelated keys kept (model, permissions)" '[ "$(jq_ "s[\"model\"]")" = opus ] && grep -q "Bash(ls)" "$S"'
ok "own statusline saved as prev" 'grep -q MYSTATUS "$C"'
# 3 idempotent
cp "$S" "$T/a"; i >/dev/null; i >/dev/null; ok "install x3 idempotent (hooks identical)" 'cmp -s "$S" "$T/a"'
ok "prev statusline survives reinstall" 'grep -q MYSTATUS "$C" && ! grep -q tz-status "$C"'
# 4 uninstall restores
i --uninstall >/dev/null; ok "uninstall: tz gone, foreign Stop + keep hook + statusline back" '! grep -q token-zombie "$S" && grep -q "echo mine" "$S" && grep -q "echo keep" "$S" && [ "$(jq_ "s[\"statusLine\"][\"command\"]")" = "echo MYSTATUS" ]'
i --uninstall >/dev/null; ok "uninstall twice is a no-op, exit 0" '[ $? = 0 ] && grep -q "echo mine" "$S"'
# 5 upgrade from v0.1 layout (5 events, 3x guard, no Stop/SessionEnd)
new 5; python3 - "$S" "$Z" <<'PY'
import json,sys
d=sys.argv[2];g=f'python3 "{d}/bin/tz-guard.py"'
mk=lambda c,m=None:dict(({'matcher':m} if m is not None else {}),hooks=[{'type':'command','command':c,'timeout':5}])
json.dump({'hooks':{'UserPromptSubmit':[mk(g)],'PostToolUse':[mk(g,'')],'PreToolUse':[mk(g,'Read')],'SessionStart':[mk(f'python3 "{d}/bin/tz-start.py"')],'PreCompact':[mk(f'python3 "{d}/bin/tz-compact.py"')]},'statusLine':{'type':'command','command':f'python3 "{d}/bin/tz-status.py"'}},open(sys.argv[1],'w'))
PY
mkdir -p "$H/.claude/token-zombie"; echo '{"prev_statusline":"echo OLD","limit":90000}' >"$C"; i >/dev/null
ok "upgrade: now 18 events, no duplicates, tz-guard x17" '[ "$(jq_ "len(s[\"hooks\"])")" = 18 ] && [ "$(grep -c "tz-guard.py" "$S")" = 17 ]'
ok "upgrade keeps prev_statusline and user config" 'grep -q "echo OLD" "$C" && grep -q 90000 "$C"'
# 6 malformed settings / config / shapes: refuse, nothing changed
new 6; echo '{bad' >"$S"; cp "$S" "$T/b"; o=$(i); ok "malformed settings refused, untouched, no backup" '[[ $o == *"not valid JSON"* ]] && cmp -s "$S" "$T/b" && ! ls "$S".bak-tz-* 2>/dev/null'
echo '[1,2]' >"$S"; o=$(i); ok "settings array refused" '[[ $o == *"unexpected shape"* ]]'
echo '{"hooks":{"Stop":"nope"}}' >"$S"; cp "$S" "$T/c"; o=$(i); ok "hooks.Stop wrong type refused, untouched" '[[ $o == *"unexpected shape"* ]] && cmp -s "$S" "$T/c"'
echo '{}' >"$S"; mkdir -p "$H/.claude/token-zombie"; echo '{oops' >"$C"; cp "$C" "$T/d"; o=$(i); ok "malformed tz config refused, config + settings untouched" '[[ $o == *"not a valid JSON"* ]] && cmp -s "$C" "$T/d" && [ "$(cat "$S")" = "{}" ]'
# 7 interrupted install: crash before replace
new 7; echo "$FOREIGN" >"$S"; cp "$S" "$T/e"; TZ_INSTALL_CRASH=1 HOME="$H" bash "$Z/install.sh" >/dev/null 2>&1; r=$?
ok "crash mid-install: exit non-zero, settings byte-identical" '[ $r != 0 ] && cmp -s "$S" "$T/e"'
ok "crash left a backup + stale tmp, next run recovers" 'ls "$S".bak-tz-* >/dev/null && [ -f "$S.tz-tmp" ] && i >/dev/null && [ ! -f "$S.tz-tmp" ] && grep -q tz-guard "$S"'
# 8 failure -> rollback (unwritable directory)
new 8; echo "$FOREIGN" >"$S"; cp "$S" "$T/f"; chmod 555 "$H/.claude"; o=$(i); r=$?; chmod 755 "$H/.claude"
ok "unwritable dir: install fails cleanly, settings unchanged" '[[ $o == *"failed"* || $o == *rror* ]] && cmp -s "$S" "$T/f"'
# 9 restore
new 9; echo "$FOREIGN" | sed "s#/x/token-zombie/bin/tz-guard.py#/x/other.py#" >"$S"; cp "$S" "$T/g"; i >/dev/null; sleep 1; i >/dev/null; i --restore >/dev/null
ok "restore after install x2 returns original bytes" 'cmp -s "$S" "$T/g"'
ok "restore refuses corrupt backup" 'new 10; echo "{x" >"$S.bak-tz-1"; ! HOME="$H" bash "$Z/install.sh" --restore >/dev/null 2>&1'
# 10 dry-run never writes anywhere
new 11; echo "$FOREIGN" >"$S"; cp "$S" "$T/h"; i --dry-run >/dev/null; ok "dry-run writes nothing (settings, backups, state dir)" 'cmp -s "$S" "$T/h" && [ -z "$(ls "$H/.claude" | grep -v settings.json)" ]'
echo "install2: pass $pass fail $fail"; [ $fail = 0 ]
