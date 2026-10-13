import SwiftUI

struct DecisionLedger: View {
    let records: [DecisionRecord]
    @ObservedObject var filters: WorkspaceFilters
    let onSelect: (DecisionRecord) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .bottom, spacing: 16) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Search").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                    TextField("Action, actor or decision ID", text: $filters.search).textFieldStyle(.roundedBorder)
                }
                VStack(alignment: .leading, spacing: 6) {
                    Text("Outcome").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                    Picker("Outcome", selection: $filters.outcome) {
                        Text("All outcomes").tag("all")
                        Text("Permit").tag("permit")
                        Text("Deny").tag("deny")
                    }.labelsHidden().frame(width: 180)
                }
            }.controlSize(.large)
            Text("\(records.count) matching decision entries · Select a row to inspect its evidence.")
                .font(.system(.caption, design: .monospaced)).foregroundStyle(.secondary)
            VStack(spacing: 0) {
                HStack(spacing: 16) {
                    Text("DECISION ID").frame(width: 135, alignment: .leading)
                    Text("RECORDED").frame(width: 160, alignment: .leading)
                    Text("ACTION").frame(maxWidth: .infinity, alignment: .leading)
                    Text("RISK").frame(width: 50, alignment: .leading)
                    Text("OUTCOME").frame(width: 90, alignment: .leading)
                    Text("ORIGIN").frame(width: 145, alignment: .leading)
                    Color.clear.frame(width: 12, height: 1)
                }
                .font(.system(.caption2, design: .monospaced).weight(.semibold))
                .foregroundStyle(.secondary).padding(16)
                .background(.primary.opacity(0.035))
                if records.isEmpty {
                    VStack(spacing: 8) {
                        Text(filters.search.isEmpty && filters.outcome == "all" ? "No decisions yet" : "No matching decisions").font(.headline)
                        Text(filters.search.isEmpty && filters.outcome == "all" ? "Run the policy example above to see a permitted read and a denied delete." : "Try another search or show all outcomes.")
                            .foregroundStyle(.secondary)
                    }.padding(36).frame(maxWidth: .infinity)
                } else {
                    ForEach(records) { record in
                        Divider()
                        Button { onSelect(record) } label: { DecisionLedgerRow(record: record) }
                            .buttonStyle(.plain)
                            .accessibilityLabel("\(record.action), \(record.outcome), by \(record.actor). Inspect evidence.")
                    }
                }
            }
            .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 12))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay { RoundedRectangle(cornerRadius: 12).strokeBorder(.primary.opacity(0.10)) }
        }
    }
}

struct DecisionLedgerRow: View {
    let record: DecisionRecord
    var body: some View {
        HStack(spacing: 16) {
            Text(record.decisionID).font(.system(.caption, design: .monospaced).weight(.semibold))
                .foregroundStyle(.tint).lineLimit(1).truncationMode(.middle).frame(width: 135, alignment: .leading)
            Text(record.timeLabel).font(.system(.caption, design: .monospaced))
                .foregroundStyle(.secondary).frame(width: 160, alignment: .leading)
            VStack(alignment: .leading, spacing: 4) {
                Text(record.action).fontWeight(.medium)
                Text("by \(record.actor)").font(.caption).foregroundStyle(.secondary)
            }.frame(maxWidth: .infinity, alignment: .leading)
            Text(record.risk).font(.caption).foregroundStyle(.secondary).frame(width: 50, alignment: .leading)
            Label(record.outcome.capitalized, systemImage: record.outcome == "permit" ? "checkmark.circle.fill" : "xmark.circle.fill")
                .font(.caption.weight(.semibold)).foregroundStyle(record.outcome == "permit" ? .green : .red)
                .frame(width: 90, alignment: .leading)
            Text(record.source == "policy_engine" ? "Policy decision" : record.source == "synthetic_seed" ? "Synthetic example" : record.source)
                .font(.caption).foregroundStyle(.secondary).frame(width: 145, alignment: .leading)
            Image(systemName: "chevron.right").font(.caption2).foregroundStyle(.tertiary).frame(width: 12)
        }.padding(16).frame(minHeight: 68).contentShape(Rectangle())
    }
}
