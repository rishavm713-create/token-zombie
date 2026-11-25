# Group 1 status (branch tz-repos-g1)
Run any test: `python3 tests/v21/test_g01_<name>.py` (standalone script).

| Repo | Status | Module / test | Result |
|---|---|---|---|
| oh-my-claudecode | ported | bin/tzteam.py, test_g01_omc.py | pass 87 fail 0 |
| ast-grep | ported | bin/tzsg.py, test_g01_astgrep.py | pass 94 fail 0 |
| beads | ported | bin/tzbeads.py, test_g01_beads.py | pass 80 fail 0 |
| ccusage | ported | bin/tzccu.py, test_g01_ccusage.py | pass 44 fail 0 |
| headroom | ported | bin/tzlogc.py (+tzcrush), test_g01_headroom.py | pass 39 fail 0 |
| cc-safety-net | covered | bin/tzshell.py, tests/v21/test_shell_parity.py | existing tests |
| everything-claude-code | ported (recheck) | bin/tzbudget.py, test_g01_tokenbudget.py | pass 15 fail 0; token-budget-advisor, MIT. Other ECC items (context-gate, strategic-compact, cost-tracker) already covered by tzgate/tzcont/tzusage |
| anthropics/skills | no code (recheck) | document/design skills, no root licence; nothing token-saving |
| token-optimizer | idea-only (recheck) | PolyForm NC; dup-read/MCP advice already rebuilt (tztoolprune) |
| Claude-BugHunter | no code (recheck) | LICENSE is MIT (ledger said none); content is bug-bounty/security methodology, not token-saving |
| humanlayer | no code | Apache-2.0 idea-only; claim lease already in tzagent (LEDGER #31) | n/a |
| karpathy-skills | no code | idea-only; refactor rules already in tz-craft (LEDGER #11) | n/a |

ccusage fix: a comment in bin/tzccu.py contained the word "requests", tripping the offline-source check; reworded.
Licences: third_party/*/LICENSE. Nothing pushed or merged.
Studio-deferred: none.
