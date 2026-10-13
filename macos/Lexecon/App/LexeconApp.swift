import SwiftUI

#if !LEXECON_SMOKE
@main struct LexeconApp: App {
    @StateObject private var model = Workspace()
    var body: some Scene {
        WindowGroup {
            Group {
                if model.signedIn { WorkspaceView(model: model) }
                else { SignInView(model: model) }
            }
            .tint(WorkspaceColors.action)
        }
        .defaultSize(width: 1260, height: 760)
        .commands {
            CommandGroup(after: .newItem) {
                Button("Refresh Decisions") { Task { await model.refresh() } }.keyboardShortcut("r")
                    .disabled(!model.signedIn)
                Button("Verify Ledger Chain") { Task { await model.verifyChain() } }.keyboardShortcut("v", modifiers: [.command, .shift])
                    .disabled(!model.signedIn || model.role != "admin")
            }
        }
    }
}
#endif
