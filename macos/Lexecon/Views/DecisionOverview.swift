import SwiftUI

struct DecisionTimeline: View {
    let records: [DecisionRecord]
    let onSelect: (DecisionRecord) -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            if records.isEmpty { Text("Run the policy example to start the timeline.").foregroundStyle(.secondary).padding(24) }
            ForEach(records) { record in
                Button { onSelect(record) } label: {
                    HStack(spacing: 18) {
                        Image(systemName: record.outcome == "permit" ? "checkmark.circle" : "xmark.circle")
                            .foregroundStyle(record.outcome == "permit" ? .green : .red)
                        VStack(alignment: .leading, spacing: 5) {
                            Text("\(record.action) · \(record.outcome.capitalized)").font(.headline)
                            Text("\(record.actor) · \(record.timeLabel)").font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Image(systemName: "chevron.right").foregroundStyle(.secondary)
                    }.padding(20).contentShape(Rectangle())
                }.buttonStyle(.plain)
                Divider()
            }
        }.background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 12))
    }
}

struct DecisionAnalytics: View {
    let records: [DecisionRecord]
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Outcomes in loaded records").font(.title2.bold())
            Text("These counts describe the records currently loaded in this workspace.").foregroundStyle(.secondary)
            HStack(spacing: 16) {
                metric("Total decisions", value: records.count)
                metric("Permitted", value: records.filter { $0.outcome == "permit" }.count)
                metric("Denied", value: records.filter { $0.outcome == "deny" }.count)
            }
        }
    }
    private func metric(_ title: String, value: Int) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title).font(.callout).foregroundStyle(.secondary)
            Text(value.formatted()).font(.system(size: 32, weight: .semibold, design: .rounded))
        }.padding(24).frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 12))
    }
}
