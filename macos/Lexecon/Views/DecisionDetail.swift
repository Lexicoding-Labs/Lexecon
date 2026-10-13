import SwiftUI

struct DecisionDetail: View {
    let record: DecisionRecord
    @ObservedObject var model: Workspace

    var chainStatus: String { model.chainStatus }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack {
                    VStack(alignment: .leading, spacing: 5) {
                        Text(record.action.capitalized).font(.largeTitle.bold())
                        Text(record.timeLabel).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Text(record.outcome.capitalized)
                        .font(.headline).foregroundStyle(record.outcome == "permit" ? .green : .orange)
                }
                Divider()
                LabeledContent("Actor", value: record.actor)
                LabeledContent("Risk level", value: record.risk)
                LabeledContent("Evaluation source", value: record.source)
                LabeledContent("Decision ID", value: record.decisionID).textSelection(.enabled)
                LabeledContent("Ledger chain", value: chainStatus)
                Text("The outcome is recorded evidence. Chain verification is a separate check.")
                    .font(.caption).foregroundStyle(.secondary)
                DisclosureGroup("Ledger hashes") {
                    LabeledContent("Entry hash", value: record.hash).textSelection(.enabled)
                    LabeledContent("Previous hash", value: record.previousHash).textSelection(.enabled)
                }
                DisclosureGroup("Raw record JSON") {
                    Text(record.json).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                }
                Spacer()
            }.padding(24)
        }.navigationTitle("Decision Evidence")
    }
}

