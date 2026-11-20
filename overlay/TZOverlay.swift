// TOKEN ZOMBIE overlay: small always-on-top macOS window (AppKit, no dependencies). Reads status.json from disk every 3 s (no network, no AI).
// Build: bash overlay/build.sh   Run: overlay/build/TZOverlay   (--selftest prints the rendered line and exits, no window)
import AppKit
import Foundation

let stateDir = ProcessInfo.processInfo.environment["TZ_STATE_DIR"] ?? (NSHomeDirectory() + "/.claude/token-zombie")
let emoji = ["CHOMP": "🧟", "HAPPY": "😊", "ALERT": "🚨", "SLEEP": "😴", "CELEBRATE": "🎉"]

func readJSON(_ name: String) -> [String: Any] {
    guard let d = FileManager.default.contents(atPath: stateDir + "/" + name),
          let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return [:] }
    return o
}

// Same rules as bin/tzmascot.py mascot_state (pure). Activity comes from activity.json: only hook-measured, stale => UNKNOWN.
func mascot(_ s: [String: Any], _ act: String) -> String {
    if s["ts"] == nil { return "SLEEP" }
    let lv = s["level"] as? String ?? ""
    if ["CRITICAL", "EXHAUSTED", "APPROACHING LIMIT"].contains(lv) || (s["risk"] as? String) == "high" { return "ALERT" }
    if (s["task_just_done"] as? Bool) == true { return "CELEBRATE" }
    if lv == "ELEVATED" || act == "working" { return "CHOMP" }
    return lv == "NORMAL" ? "HAPPY" : "SLEEP"
}

func activity() -> String {
    let a = readJSON("activity.json")
    guard let ts = a["ts"] as? Double, let ev = a["event"] as? String else { return "UNKNOWN" }
    if ["Stop", "SessionEnd"].contains(ev) { return "idle" }
    return (Date().timeIntervalSince1970 - ts) <= 900 ? "working" : "UNKNOWN"
}

func line() -> String {
    let s = readJSON("status.json")
    let m = mascot(s, activity())
    if s.isEmpty { return "\(emoji[m]!) \(m) no status yet" }
    return "\(emoji[m]!) \(m)  \(s["level"] as? String ?? "?")  ctx \(s["ctx_pct"] as? Int ?? 0)%  risk \(s["risk"] as? String ?? "?")"
}

if CommandLine.arguments.contains("--selftest") { print(line()); exit(0) }

let app = NSApplication.shared
app.setActivationPolicy(.accessory)  // no Dock icon
let panel = NSPanel(contentRect: NSRect(x: 40, y: 80, width: 330, height: 34), styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
panel.level = .floating
panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
panel.isMovableByWindowBackground = true
panel.backgroundColor = NSColor(white: 0.08, alpha: 0.92)
let label = NSTextField(labelWithString: line())
label.textColor = .white
label.font = NSFont.monospacedSystemFont(ofSize: 13, weight: .medium)
label.frame = NSRect(x: 10, y: 7, width: 310, height: 20)
panel.contentView?.addSubview(label)
panel.orderFrontRegardless()
Timer.scheduledTimer(withTimeInterval: 3, repeats: true) { _ in label.stringValue = line() }
app.run()
