#!/usr/bin/env python3
"""Merge GitHub traffic/clones JSON (stdin) into docs/clones.json (keyed by day, so reruns never double count)."""
import json, sys, datetime, pathlib
p = pathlib.Path("docs/clones.json")
d = json.loads(p.read_text()) if p.exists() else {"days": {}}
for c in json.load(sys.stdin)["clones"]:
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
