# tz commands

Run `tz help` for the full list. Exit codes: 0 ok; 1 failure; 2 usage; 3 `status` in STOP state. See also [CLI.md](CLI.md).

| Command | What it does |
|---|---|
| `tz status` / `forecast` / `stats` | Context, tokens, burn, warn state; savings (MEASURED / EST / UNKNOWN) |
| `tz handoff` / `resume` | Save a short note; continue in a fresh chat |
| `tz recall` | Bring back trimmed output |
| `tz budget [show\|check\|set]` | Session and weekly token or USD budgets |
| `tz ccusage` | Cross-check totals against ccusage (if installed) |
| `tz claim` | Shared note board between sessions (`coord post\|list\|claim\|done`) |
| `tz stale` | Stale-branch check against a base |
| `tz clihelp` | List a Python CLI's Click commands from source |
| `tz debt` | Ledger of deliberate-shortcut code comments |
| `tz diag FILE...` | Cheap post-edit check, silent when clean |
| `tz facts` | Learned project facts (show, learn, block, forget) |
| `tz fast` | Profile a hot function, prove a rewrite; speed mode |
| `tz gitguard check "<cmd>"` | Check a git command before running it |
| `tz line` | Status line render, preview, widgets; model advice via `route` |
| `tz memsearch index\|search\|expand` | Progressive recall over Markdown notes |
| `tz obs` | Session observations from hook events (no model call) |
| `tz sandbox` | Run a script, show only a bounded part of its output |
| `tz scrub FILE...` | Replace secret values in files |
| `tz sg PATTERN [paths]` | Structural code search |
| `tz spec` | Per-change spec folders, merged into living specs |
| `tz squad list\|diff\|pause\|resume\|kill\|open` | Manage parallel agent tasks |
| `tz tbench check\|parse` | Validate benchmark task dirs, parse logs |
| `tz team "TASK" --test CMD` | Multi-worker run with test and budget limits |
| `tz trace` | Per-turn token trace from a transcript |
| `tz ts doctor\|tags\|check\|skel` | Tree-sitter style file tags and skeletons |
| `tz depth` | Response-depth budget advisor |
| `tz impact NAME` | Callers by depth, importing files, tests to run |
| `tz condense` | Condense history: keep first and last events, shrink old bulky results |
| `tz sym NAME` | Where NAME is defined (file:line) and files that use it |
