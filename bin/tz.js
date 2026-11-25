#!/usr/bin/env node
// Runs the Python `tz` CLI next to this file, passing args and exit code through.
const { spawnSync } = require("child_process");
const path = require("path");
const py = process.platform === "win32" ? ["py", "-3"] : ["python3"];
const r = spawnSync(py[0], [...py.slice(1), path.join(__dirname, "tz"), ...process.argv.slice(2)], { stdio: "inherit" });
if (r.error) {
  console.error("token-zombie: python3 is required (" + r.error.message + ")");
  process.exit(127);
}
process.exit(r.status === null ? 1 : r.status);
