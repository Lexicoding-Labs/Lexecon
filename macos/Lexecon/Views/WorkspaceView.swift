import SwiftUI

final class WorkspaceFilters: ObservableObject {
    @Published var tab = "Ledger"
    @Published var search = ""
    @Published var outcome = "all"
    @Published var showingDetail = false
}

struct WorkspaceView: View {
    @ObservedObject var model: Workspace
    @StateObject private var filters = WorkspaceFilters()
    @Environment(\.colorScheme) private var colorScheme

    private var brand: Color { colorScheme == .dark ? Color(red: 0.47, green: 0.79, blue: 0.66) : Color(red: 0.14, green: 0.37, blue: 0.30) }
    private var canvas: Color { colorScheme == .dark ? Color(red: 0.08, green: 0.105, blue: 0.095) : Color(red: 0.955, green: 0.965, blue: 0.949) }
    private var filtered: [DecisionRecord] {
        model.records.filter {
            (filters.outcome == "all" || $0.outcome == filters.outcome) &&
            (filters.search.isEmpty || $0.searchText.localizedCaseInsensitiveContains(filters.search))
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                pageHeading
                statusStrip
                if let error = model.error {
                    Label(error, systemImage: "exclamationmark.triangle.fill")
                        .foregroundStyle(.red).textSelection(.enabled)
                }
                guidedExample
                if let note = model.note {
                    Text(note).font(.callout).foregroundStyle(.secondary).textSelection(.enabled)
                }
                HStack(spacing: 24) {
                    ForEach(["Ledger", "Timeline", "Analytics", "Exports"], id: \.self) { tab in
                        Button { filters.tab = tab } label: {
                            VStack(spacing: 10) {
                                Text(tab).fontWeight(filters.tab == tab ? .semibold : .medium)
                                Rectangle().fill(filters.tab == tab ? brand : .clear).frame(height: 2)
                            }.fixedSize(horizontal: true, vertical: false)
                        }
                        .buttonStyle(.plain)
                        .foregroundStyle(filters.tab == tab ? brand : .secondary)
                        .accessibilityAddTraits(filters.tab == tab ? .isSelected : [])
                    }
                    Spacer()
                }.overlay(alignment: .bottom) { Divider() }
                tabContent
                Text("Local workspace · \(model.username) · Records are evidence of a policy result; no external tool runs here.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            .padding(32)
            .frame(maxWidth: 1360, alignment: .leading)
            .frame(maxWidth: .infinity)
        }
        .background(canvas)
        .tint(brand)
        .navigationTitle("Lexecon")
        .navigationSubtitle("Local workspace")
        .toolbar { WorkspaceToolbar(model: model) }
        .alert("Replace the current policy?", isPresented: $model.confirmReplacement) {
            Button("Cancel", role: .cancel) { }
            Button("Replace and Run") { Task { await model.runExample() } }
        } message: { Text("The guided example replaces the policy currently loaded in memory. Existing ledger records remain.") }
        .sheet(isPresented: $filters.showingDetail) {
            VStack(spacing: 0) {
                HStack {
                    Text("Decision details").font(.headline)
                    Spacer()
                    Button("Done") { filters.showingDetail = false }.keyboardShortcut(.cancelAction)
                }.padding(20)
                Divider()
                if let record = model.selectedRecord {
                    DecisionDetail(record: record, model: model)
                }
            }.frame(width: 680, height: 620)
        }
        .fileExporter(isPresented: $model.showingExporter,
                      document: model.exportData.map(EvidenceDocument.init(bytes:)),
                      contentType: .zip,
                      defaultFilename: "lexecon-evidence-\(Date.now.formatted(.iso8601.year().month().day().dateSeparator(.dash))).zip") { result in
            switch result {
            case .success: model.note = "Evidence ZIP saved. Verify the saved file with scripts/verify-evidence-zip.py."
            case .failure(let error): model.error = error.localizedDescription
            }
        }
        .frame(minWidth: 960, minHeight: 620)
    }

    private var pageHeading: some View {
        HStack(alignment: .bottom, spacing: 24) {
            VStack(alignment: .leading, spacing: 8) {
                Text("POLICY / EVIDENCE").font(.system(.caption, design: .monospaced).weight(.semibold)).tracking(1.8).foregroundStyle(brand)
                Text("Decisions").font(.system(size: 36, weight: .bold, design: .rounded))
                Text("Policy outcomes and ledger evidence from this local workspace.").foregroundStyle(.secondary)
            }
            Spacer(minLength: 12)
            DashboardActions(model: model)
        }
    }

    private var statusStrip: some View {
        HStack(spacing: 24) {
            Text("\(model.records.count) loaded decisions").fontWeight(.semibold)
            Label(model.chainStatus, systemImage: model.chainStatus == "Chain verified" ? "checkmark.seal" : "link")
                .foregroundStyle(model.chainStatus == "Chain failed verification" ? Color.red : .secondary)
            Spacer()
            if model.busy { ProgressView().controlSize(.small) }
            Button("Refresh ledger") { Task { await model.refresh() } }
                .buttonStyle(.plain).foregroundStyle(brand).disabled(model.busy)
        }
        .font(.system(.caption, design: .monospaced))
        .padding(.vertical, 14)
        .overlay(alignment: .top) { Divider() }
        .overlay(alignment: .bottom) { Divider() }
    }

    private var guidedExample: some View {
        HStack(spacing: 28) {
            VStack(alignment: .leading, spacing: 8) {
                Text("TRY THE WORKFLOW").font(.system(.caption2, design: .monospaced).weight(.semibold)).tracking(1.5).foregroundStyle(brand)
                Text("Run a policy example").font(.headline)
                Text("Load an in-memory policy, request a permitted read and a denied delete, then compare both responses with ledger records. No tool executes.")
                    .font(.callout).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
            Button(model.busy ? "Working…" : "Run policy example") { Task { await model.prepareExample() } }
                .buttonStyle(.borderedProminent).controlSize(.large)
                .tint(WorkspaceColors.action)
                .disabled(model.busy || model.role != "admin")
                .help(model.role == "admin" ? "Run the read/deny example" : "Only an administrator can load the example policy")
        }
        .padding(22)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 14))
        .overlay { RoundedRectangle(cornerRadius: 14).strokeBorder(.primary.opacity(0.10)) }
    }

    @ViewBuilder private var tabContent: some View {
        switch filters.tab {
        case "Timeline": DecisionTimeline(records: model.records, onSelect: inspect)
        case "Analytics": DecisionAnalytics(records: model.records)
        case "Exports":
            VStack(alignment: .leading, spacing: 14) {
                Text("Take the evidence with you").font(.title2.bold())
                Text("Export a ZIP of recorded events and their manifest. Rehashing the saved ZIP checks its contents; signer identity and full-chain continuity need separate verification.")
                    .foregroundStyle(.secondary)
                Button("Export evidence ZIP", systemImage: "square.and.arrow.up") { Task { await model.export() } }
                    .buttonStyle(.borderedProminent).controlSize(.large).tint(WorkspaceColors.action).disabled(model.busy)
            }.padding(24).frame(maxWidth: .infinity, alignment: .leading)
                .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 14))
        default:
            DecisionLedger(records: filtered, filters: filters, onSelect: inspect)
        }
    }

    private func inspect(_ record: DecisionRecord) {
        model.selectedID = record.id
        filters.showingDetail = true
    }
}
