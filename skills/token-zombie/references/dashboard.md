# Dashboard, companion, in-chat panel
- `tz dash --out F.html` writes a static self-contained page (no external requests); `tz dash --serve [--port N]` binds 127.0.0.1 only.
- `tz companion [--port N]`: local status server, 127.0.0.1, token auth (`~/.claude/token-zombie/companion.token`, mode 600), Host-header check and CSP.
- `tz mascot`: zombie state line (5 states). `tz overlay build|run`: native macOS window via Command Line Tools swiftc; not visually verified.
- In-chat panel: the plugin's `hooks/panel.tsx` Mod; details in docs/PANEL.md.
