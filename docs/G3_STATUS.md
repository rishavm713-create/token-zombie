# Group 3 status (branch feat/v2.1-repos-g3)
Run each as a script: `python3 tests/v21/test_g03_<name>.py` (all pass, fail 0, 2026-11-25).

| Repo | Module | Test | Result |
|---|---|---|---|
| ruflo | bin/tzbudget.py | test_g03_ruflo.py | pass 57 |
| ccstatusline | bin/tzline.py | test_g03_ccstatusline.py | pass 8 |
| claude-squad | bin/tzsquad.py | test_g03_claude_squad.py | pass 45 |
| claude-mem | bin/tzobs.py | test_g03_claude_mem.py | pass 94 (prompt recording OFF by default) |
| tree-sitter | bin/tzts.py | test_g03_tree_sitter.py | pass 49 (real tree_sitter case SKIPPED: not installed) |
| claw-code | bin/tzclaw.py | test_g03_claw_code.py | pass 60 |
| vercel agent-skills | bin/tzskillcheck.py, skills/tz-craft/references | test_g03_agent_skills.py | pass 40 |
| lean-ctx | bin/tzout.py `_reread` (existing) | test_g03_lean_ctx.py | pass 5 |
| memsearch | bin/tzmemsearch.py | test_g03_memsearch.py | pass 50 |

Fixes: memsearch test used a 1-char body ('W'), which `_meaningful` drops by design -> now 'World'; prune test expected 2 removed but day + copy.md = 4 chunks.
New: test_g03_ccstatusline.py, test_g03_lean_ctx.py (no new module needed). Not run: Windows, full run_all.sh.
