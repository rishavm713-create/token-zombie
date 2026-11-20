#!/bin/bash
# Task 2 acceptance: --format csv|text on the CLI; default output unchanged; tests for csv exist and pass.
cd "$1" || exit 2; f=0
python3 -m unittest discover -s tests -q 2>/dev/null || { echo "tests FAIL"; f=1; }
t=$(python3 -m statlib.cli data/sample.csv); c=$(python3 -m statlib.cli data/sample.csv --format csv)
[ "$(echo "$c" | head -1)" = "metric,value" ] || { echo "csv header wrong"; f=1; }
[ "$(echo "$c" | wc -l | tr -d ' ')" = 5 ] || { echo "csv rows wrong"; f=1; }
echo "$c" | grep -q '^mean,' || { echo "csv mean row"; f=1; }
[[ "$t" == mean:* ]] || { echo "text default changed"; f=1; }
[ "$(python3 -m statlib.cli data/sample.csv --format text)" = "$t" ] || { echo "--format text differs"; f=1; }
grep -rqi "csv" tests/*.py || { echo "no csv test"; f=1; }
[ $f = 0 ] && echo ACCEPT || echo REJECT; exit $f
