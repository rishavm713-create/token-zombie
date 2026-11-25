<p align="center"><picture><source media="(prefers-color-scheme: light)" srcset="docs/img/logo-light.svg"><img src="docs/img/logo.svg" width="480" alt="TOKEN ZOMBIE"></picture></p>

<h1 align="center">🧟 Stop wasting your Claude Code limit</h1>

<p align="center">Claude Code re-reads the same things again and again and burns your usage.<br><b>TOKEN ZOMBIE stops that.</b> 💸 Free · 🔒 Stays on your computer · 🚫 No tracking</p>

<p align="center">Claude Code token optimization: context management, usage tracking and session handoff in one local plugin.</p>

<p align="center"><img src="https://img.shields.io/badge/tests-3693%20pass-83ffa0" alt="3693 tests pass"> <img src="https://img.shields.io/badge/made%20with-Claude%20Code-d97757" alt="Made with Claude Code"> <img src="https://img.shields.io/badge/macOS-supported-83ffa0" alt="macOS"> <img src="https://img.shields.io/badge/Linux-supported-83ffa0" alt="Linux"> <img src="https://img.shields.io/badge/Windows-beta-f0b429" alt="Windows beta"> <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-4c9a1a" alt="MIT"></a></p>

## 🚀 Install (30 seconds)

Paste these two lines into Claude Code (the chat box), then restart Claude Code. That's it.

```
/plugin marketplace add rishavm713-create/token-zombie
/plugin install token-zombie@token-zombie
```

↩️ Don't like it? Remove it any time: `/plugin uninstall token-zombie`

![TOKEN ZOMBIE demo](docs/img/demo-live.svg)

## 🤔 What do I get?

| ✨ Feature | 💬 In plain words |
|---|---|
| ✂️ **Less noise** | Long, messy output is trimmed. Nothing is lost: ask for it back any time. |
| ⚠️ **Early warnings** | Told before a chat gets too big or goes in circles. |
| 💾 **Never lose your place** | One command saves where you stopped; a fresh chat picks it up. |
| 🔍 **Honest numbers** | Every number says if it was measured or estimated. |

## ✨ Everything it does

- 💸 **Saves tokens:** trims noisy output (get it back any time with `tz recall`), spots repeated reads, suggests cheaper models, tracks cost.
- ⚠️ **Warns early:** before a chat gets too big or loops. `tz budget` shows your limit.
- 🛡️ **Stays safe:** stops risky commands like `rm -rf /` and false "done" claims.
- 💾 **Never loses your place:** `tz handoff` saves it, `tz resume` continues in a fresh chat.
- 🧭 **Plans and ships:** `tz code` plans, `tz split` finds parallel work, `tz pr` prepares pull requests.
- 🔍 **Honest numbers:** measured or estimated, always labelled.

## 🧩 All 69 things it does

<details><summary>Show the full list</summary>

**Understand**

1. Understand the codebase
2. Map files, folders, dependencies
3. Remember conversations and decisions
4. Retrieve project knowledge automatically
5. Remember unfinished tasks
6. Understand existing coding standards
7. Avoid rediscovering what is known

**Save**

8. Compress terminal output
9. Remove irrelevant tool-result info
10. Detect repeated commands and outputs
11. Keep important errors and warnings
12. Store big outputs, retrieve on demand
13. Track every token (all logs, by model/day/category)
14. Track actual and estimated cost
15. Recommend cheaper models
16. Measure whether savings are real

**Execute**

17. Understand large tasks
18. Break tasks into smaller ones
19. Step-by-step plans
20. Find parallel tasks
21. Assign work to coding agents
22. Monitor agents
23. Detect duplicated work
24. Collect agent results
25. Coordinate agents with each other
26. Recover interrupted tasks

**Build**

27. Help build complete apps
28. Coordinate frontend and backend
29. Build APIs and integrations
30. Database architecture
31. Consistency across files
32. Follow project architecture
33. Find missing implementation pieces
34. Continue across sessions

**Test**

35. Run relevant tests
36. Detect bugs and failures
37. Inspect code changes
38. Find missing features
39. Check security risks
40. Help fix errors
41. Re-run failed tests
42. Verify fixes worked
43. Block false completion claims

**Keep**

44. Auto checkpoints
45. Preserve decisions
46. Save unfinished work
47. Recover earlier task states
48. Detailed handoffs
49. Continue after interruptions
50. Prevent repetition

**Workflow**

51. Prepare Git commits
52. Create and manage branches
53. Prepare pull requests
54. Implementation reports
55. Track outstanding tasks
56. Prepare projects for delivery
57. Approval for sensitive operations
58. Verify before declaring complete

**Control**

59. Show active agents
60. Show current tasks
61. Show token use
62. Show cost and savings
63. Show optimization activity
64. Show test results
65. Show checkpoint status
66. Show outstanding work
67. Show completion progress

**Meta**

68. Live status board of all 69 (this list)
69. Test that fails if a DONE row has no real command

</details>

## 📊 In one test session

| 📋 What we measured | Result |
|---|---:|
| 🧹 Noise kept out | **54,852 characters** |
| ⚙️ Cost of TZ itself | 1,880 characters |
| 🎯 False alarms / misses | **0 / 0** |

| 💾 Saved today (measured) | **291.7K tokens** across 563 optimizations |

👉 See **your** number: type `tz gain`

Noise is counted in characters, savings in tokens, and each number is labelled measured or estimated. Results vary by workflow, so no fixed saving is promised: see the [benchmark method](docs/BENCHMARK-METHOD.md).

## 📚 Learn more

🌐 [Website](https://rishavm713-create.github.io/token-zombie/) · 📖 [Full guide](docs/REFERENCE.md) · ✅ [Test evidence](docs/TEST_EVIDENCE.md) · 🔐 [Security](.github/SECURITY.md) · 🤝 [Contribute](.github/CONTRIBUTING.md)

Created by [Rishav Mishra](https://github.com/rishavm713-create) · MIT · macOS and Linux (Windows beta)
