# Model routing
`tz route <prompt> [--model M]` gives model advice (haiku / sonnet / opus) and complexity 1-5, logged to `routing.jsonl`. Costs are EST. It is advice: tz cannot switch the running chat's model.
Rules: main chat Sonnet; Opus only for hard builds/design; Haiku for search, bulk reading, web/GitHub; subagents default to Haiku when the task is reading-heavy. `tz classify <words>` shows task mode.
