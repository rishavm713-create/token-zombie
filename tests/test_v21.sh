#!/bin/bash
# v2.1 integration tests (tests/v21/test_*.py): each feature vs the original tool's behaviour + conflict checks. Fake HOME per file.
D="$(cd "$(dirname "$0")" && pwd)/v21"; P=0; F=0
for f in "$D"/test_*.py; do
  out=$(cd "$D" && HOME="$(mktemp -d)" TZ_DEDUPE=0 python3 "$(basename "$f")" 2>&1); echo "$out" | grep -E '^(FAIL|SKIP)'
  line=$(echo "$out" | grep -E '^pass [0-9]+ fail [0-9]+' | tail -1); [ -z "$line" ] && { echo "FAIL: $(basename "$f") crashed"; echo "$out" | tail -${TZ_SUITE_VERBOSE:+30}5; F=$((F+1)); continue; }
  P=$((P+$(echo "$line" | cut -d' ' -f2))); F=$((F+$(echo "$line" | cut -d' ' -f4)))
  [ -n "$TZ_SUITE_VERBOSE" ] && [ "$(echo "$line" | cut -d' ' -f4)" != 0 ] && echo "$out" | grep -v '^ok' | tail -40 | sed "s/^/  | $(basename "$f") | /"
done
echo "pass $P fail $F"; [ $F = 0 ]
