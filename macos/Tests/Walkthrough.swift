// Offline presentation harness. Never compiled into the production application.
import SwiftUI
import AppKit

@main enum OfflineCaptureMain {
    @MainActor static func main() {
        let app = NSApplication.shared
        let delegate = CaptureDelegate()
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
        withExtendedLifetime(delegate) {}
    }
}

@MainActor final class CaptureDelegate: NSObject, NSApplicationDelegate {
    private let model = Workspace()
    private var window: NSWindow!

    func applicationDidFinishLaunching(_ notification: Notification) {
        let scene = CommandLine.arguments[1]
        model.username = "demo_admin"; model.role = "admin"
        if scene != "01-empty" {
            model.records = [("delete", "deny"), ("read", "permit")].enumerated().compactMap { index, value in
                DecisionRecord(["entry_id": "illustrative-\(index)", "timestamp": "2026-10-07T14:30:00",
                                "entry_hash": "illustrative — no hash claim", "previous_hash": "illustrative — no hash claim",
                                "data": ["actor": "demo_admin", "action": value.0, "decision": value.1,
                                         "decision_id": "example-\(value.0)", "evaluation_source": "synthetic_seed", "risk_level": 1]])
            }
        }
        let view = WorkspaceView(model: model)
            .safeAreaInset(edge: .bottom) {
                Text("ILLUSTRATIVE DEMO · SAMPLE RECORDS · NO API CONNECTION")
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(.secondary).padding(7)
                    .frame(maxWidth: .infinity)
                    .background(Color(nsColor: .windowBackgroundColor))
            }.preferredColorScheme(.light)
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1260, height: 760),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "Lexecon — Illustrative demo"
        window.contentView = NSHostingView(rootView: view)
        window.center(); window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) { [self] in
            window.makeKeyAndOrderFront(nil)
            NSApp.activate()
            window.makeFirstResponder(nil)
            switch scene {
            case "03-detail": click(470, 665)
            case "04-timeline": click(135, 392)
            case "05-analytics": click(221, 392)
            case "06-exports": click(306, 392)
            default: break
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { [self] in
                writeCaptureRequest(scene)
            }
        }
        // Safety stop if the coordinating capture process is interrupted.
        DispatchQueue.main.asyncAfter(deadline: .now() + 30) { NSApp.terminate(nil) }
    }

    private func writeCaptureRequest(_ name: String) {
        let control = URL(fileURLWithPath: CommandLine.arguments.last!, isDirectory: true)
        do {
            let data = try JSONSerialization.data(withJSONObject: ["name": name, "window": window.windowNumber,
                                                                  "pid": ProcessInfo.processInfo.processIdentifier])
            try data.write(to: control.appendingPathComponent("capture-request.json"), options: .atomic)
        } catch { fputs("Capture request failed: \(error)\n", stderr); NSApp.terminate(nil) }
    }

    // Mouse events remain inside this test process; system Accessibility is untouched.
    private func click(_ x: CGFloat, _ yFromTop: CGFloat) {
        let point = NSPoint(x: x, y: window.frame.height - yFromTop)
        for type in [NSEvent.EventType.leftMouseDown, .leftMouseUp] {
            if let event = NSEvent.mouseEvent(with: type, location: point, modifierFlags: [],
                                             timestamp: ProcessInfo.processInfo.systemUptime,
                                             windowNumber: window.windowNumber, context: nil,
                                             eventNumber: 0, clickCount: 1, pressure: 1) {
                window.sendEvent(event)
            }
        }
    }
}
