#!/bin/bash
# Full v0.1 suite: sums real pass/fail counts of every test script. Run: bash tests/run_all.sh
D="$(cd "$(dirname "$0")" && pwd)"; P=0; F=0
for t in test_tz test_continuity test_usage test_opt test_cap test_cli test_install test_bench test_auto test_ab test_sup test_e2e test_install2 test_hard test_status_read test_modes test_plugin test_host test_dash2 test_repo test_live test_out test_vet test_smoke test_next; do
  [ -f "$D/$t.sh" ] || continue
  out=$(bash "$D/$t.sh" 2>&1); echo "$out" | grep '^FAIL' ; line=$(echo "$out" | grep -E 'pass[ :]+[0-9]+' | tail -1)
  p=$(echo "$line" | sed -E 's/.*pass[ :]+([0-9]+).*/\1/'); f=$(echo "$line" | sed -E 's/.*fail[ :]+([0-9]+).*/\1/')
  echo "$t: $line"; P=$((P+${p:-0})); F=$((F+${f:-0}))
done
echo "TOTAL pass $P fail $F"; [ $F = 0 ]
