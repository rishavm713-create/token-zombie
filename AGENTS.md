# TOKEN ZOMBIE project
When the owner says "continue tz project" (or anything like it): read handoffs/CONTINUE.md first, then only the files it names. Do not re-derive context.

HARD RULE (owner 2026-11-25): never edit `hooks/` without running `claude plugin test .` and `bash tests/test_barguard.sh`; never leave the live plugin folder (~/token-zombie-v2.1) on a non-main branch. The TZ bar must always render: no unguarded Node globals (`process`, `require`, `Buffer`, `__dirname`) in `hooks/panel.tsx` or its imports.
