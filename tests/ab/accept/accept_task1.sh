#!/bin/bash
# Task 1 acceptance: run in the finished project dir ($1). Visible tests pass, hidden cases pass, test files untouched.
cd "$1" || exit 2; f=0
python3 -m unittest discover -s tests -q 2>/dev/null || { echo "visible tests FAIL"; f=1; }
python3 - <<'PY' || f=1
from statlib import stats as s
assert s.median([5, 1, 3, 2]) == 2.5 and s.median([7]) == 7
assert abs(s.variance([1, 2, 3, 4, 5]) - 2.5) < 1e-9
assert abs(s.percentile([10, 20, 30, 40, 50], 90) - 46.0) < 1e-9 and s.percentile([1, 2, 3], 0) == 1 and s.percentile([1, 2, 3], 100) == 3
print("hidden cases ok")
PY
[ "$(git diff --stat -- tests | wc -l | tr -d ' ')" = 0 ] || { echo "tests were modified"; f=1; }
[ $f = 0 ] && echo ACCEPT || echo REJECT; exit $f
