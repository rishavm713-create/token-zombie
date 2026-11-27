#!/usr/bin/env python3
"""Merge GitHub traffic/clones JSON (stdin) into docs/clones.json (keyed by day, so reruns never double count)."""
import json, sys, datetime, pathlib
p = pathlib.Path("docs/clones.json")
d = json.loads(p.read_text()) if p.exists() else {"days": {}}
t = json.load(sys.stdin)
# GitHub only gives uniques for a rolling 14 days. Add each run's rise over the last run's value
# to a running total that never goes down (approximate: drops are ignored, repeat cloners may recount).
last = d.get("unique_last", d.get("unique14", 0))
d["unique14"] = d.get("unique14", 0) + max(0, t["uniques"] - last)
d["unique_last"] = t["uniques"]
for c in t["clones"]:
    day = c["timestamp"][:10]
    # keep the larger value: the newest partial day grows, older days are final
    d["days"][day] = max(d["days"].get(day, 0), c["count"])
d["total"] = sum(d["days"].values())
d["since"] = min(d["days"])
d["updated"] = datetime.date.today().isoformat()
p.write_text(json.dumps(d, indent=1, sort_keys=True) + "\n")
pathlib.Path("docs/clones-badge.json").write_text(json.dumps(
    {"schemaVersion": 1, "label": "git clones", "message": f"{d['total']:,}", "color": "informational"}) + "\n")
print(d["total"], "clones since", d["since"])
