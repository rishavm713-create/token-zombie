# Reuse register (TOKEN ZOMBIE is MIT)
The rule: reuse working code when its licence allows it and it does not duplicate TZ. Keep the copyright notice, the licence
file and the attribution with any copied file. For a restrictive licence, study the ideas and write our own code.
Reviewed 2026-11-21. Code was read at these versions: caveman 4.0.1, ponytail 5.3.2, token-optimizer 5.13.63,
claude-mem 16.0.2, rtk 1.1.0, and GitHub HEAD of context-mode, serena, claude-context and pxpipe.

## Register
| Repo | Licence | Source looked at | Reused | How / modifications | Obligations |
|---|---|---|---|---|---|
| rtk-ai/rtk | Apache-2.0 | src/hooks/decision.rs, hook_cmd.rs, src/discover/registry.rs, core/telemetry.rs | YES, by invocation | `tz stats` runs `rtk gain -f json` (bin/tzopt.py `rtk_gain`). No code copied. TZ never filters Bash, so the savings are not counted twice. | None while TZ only calls the installed binary. If rtk is ever bundled: ship its LICENSE + NOTICE. |
| JuliusBrussee/caveman | Apache-2.0 | src/hooks/caveman-activate.js, caveman-mode-tracker.js, caveman-stats.js | No | Its transcript usage parser duplicates bin/tzusage.py. The hooks are mode text, which TZ does not need. | If copied: LICENSE + NOTICE, mark changed files. |
| DietrichGebert/ponytail | MIT | hooks/ponytail-activate.js, ponytail-mode-tracker.js | No | Nothing missing in TZ. | If copied: keep its MIT notice. |
| thedotmack/claude-mem | Apache-2.0 | scripts/*.cjs (minified bundles, 0.8-2.2 MB) | No | Bundles can't be audited and the source isn't in the cache. Each tool call costs an extra model call. TZ handoffs are cheaper. | n/a |
| zilliztech/claude-context | MIT | packages/mcp/src (4 tools), embedding providers | No | Sends code to cloud embedding services, which breaks local-first. Owner decision: not integrated. | n/a |
| teamchong/pxpipe | MIT | src/node.ts (API proxy :47821), src/core/* | No | Proxies every API request and key, and its compression is lossy. Owner decision: not integrated. | n/a |
| karpathy-guidelines (local skill, ~/.claude/skills) | MIT | SKILL.md | Text ideas | skills/token-zombie/references/engineering.md, already attributed. | Attribution kept. |
| mksglu/context-mode | Elastic-2.0 | src/adapters/claude-code.ts, src/core/policy/read-deny.ts, src/prompt/*.md | Ideas only | bin/tzout.py is our own code from the idea "trim big tool output, keep the full text locally, recall it". No ELv2 code or text copied. | ELv2 code can't be relicensed MIT: do not copy. |
| alexgreensh/token-optimizer | PolyForm-Noncommercial-1.0.0 | skills/token-optimizer/scripts/read_cache.py, bash_hook.py, hooks/*_runner.py | Ideas only | tzopt.read_decision (deny an unchanged re-read once) is our own code. No PolyForm code copied. | Noncommercial: never copy. |
| oraios/serena | GPL-3.0 (SolidLSP MIT) | src/serena/tools (51 MCP tools) | No | 51-tool schema costs more than it saves on small repos. Owner decision: not integrated. | GPL: never copy into MIT. |

## Benchmark: rtk vs TZ's own filter (same output, chars, this repo, 2026-11-21)
| Command | raw | rtk | `tz filter` |
|---|---|---|---|
| `grep -rn def bin` | 14580 | 10127 (groups by file, keeps every match) | 2098 (keeps 40 lines: lossy) |
| `git log -n 100 --stat` | 16368 | 16368 (no rule for --stat) | 2147 (lossy) |
| `ls -la bin tests` | 3406 | n/a | 2113 |
The two tools do different jobs: rtk keeps the content and runs automatically on Bash, while `tz filter` cuts hard and only
runs when asked. Keep rtk for Bash and `tz filter` as a manual tool, and never run both on the same output.

## What TZ wrote itself (and why)
- bin/tzout.py: no compatible implementation exists for Python + Claude Code `updatedToolOutput`. context-mode is ELv2 and
  rtk is Rust and Bash-only.
- tzopt.read_decision: builds on TZ's own read_advice hash cache. token-optimizer's version is noncommercial.
- tz-vet LOW tier and the tzcap skill usage scan: no equivalent found in any repo above.
