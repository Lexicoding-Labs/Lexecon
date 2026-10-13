import SwiftUI

enum WorkspaceColors {
    static let action = Color(red: 0.14, green: 0.37, blue: 0.30)
}

struct WorkspaceToolbar: ToolbarContent {
    @ObservedObject var model: Workspace

    var body: some ToolbarContent {
        ToolbarItem(placement: .primaryAction) {
            Menu {
                Text("\(model.username) · \(model.role)")
                Divider()
                Button("Sign Out", systemImage: "rectangle.portrait.and.arrow.right") {
                    Task { await model.signOut() }
                }.disabled(model.busy)
            } label: { Label("Account", systemImage: "person.crop.circle") }
                .help("Account and sign out")
        }
    }
}

/// Glass accents the primary actions; the dashboard and evidence remain solid.
struct DashboardActions: View {
    @ObservedObject var model: Workspace
    @Environment(\.accessibilityReduceTransparency) private var reduceTransparency

    var body: some View {
        if #available(macOS 26.0, *), !reduceTransparency {
            GlassEffectContainer(spacing: 16) {
                HStack(spacing: 12) {
                    verify.buttonStyle(.glass).tint(nil)
                    export.buttonStyle(.glassProminent).tint(WorkspaceColors.action)
                }
            }.controlSize(.large)
        } else {
            HStack(spacing: 12) {
                verify.buttonStyle(.bordered)
                export.buttonStyle(.borderedProminent).tint(WorkspaceColors.action)
            }.controlSize(.large)
        }
    }

    private var verify: some View {
        Button("Verify Integrity", systemImage: "checkmark.shield") { Task { await model.verifyChain() } }
            .disabled(model.busy || model.role != "admin")
            .help("Verify the source ledger chain (⇧⌘V)")
    }
    private var export: some View {
        Button("Export Audit", systemImage: "square.and.arrow.up") { Task { await model.export() } }
            .disabled(model.busy)
            .help("Save an evidence ZIP")
    }
}
