import Foundation

struct DecisionRecord: Identifiable {
    let id: String
    let timestamp: String
    let hash: String
    let previousHash: String
    let data: [String: Any]

    init?(_ value: Any) {
        guard let object = value as? [String: Any],
              let id = object["entry_id"] as? String,
              let data = object["data"] as? [String: Any] else { return nil }
        self.id = id
        self.timestamp = object["timestamp"] as? String ?? ""
        self.hash = object["entry_hash"] as? String ?? ""
        self.previousHash = object["previous_hash"] as? String ?? ""
        self.data = data
    }

    var action: String { data["action"] as? String ?? "Unknown" }
    var actor: String { data["actor"] as? String ?? "Unknown" }
    var outcome: String { data["decision"] as? String ?? "Unknown" }
    var source: String { data["evaluation_source"] as? String ?? "legacy / unknown" }
    var decisionID: String { data["decision_id"] as? String ?? id }
    var risk: String { String(describing: data["risk_level"] ?? "—") }
    var timeLabel: String { String(timestamp.prefix(19)).replacingOccurrences(of: "T", with: " ") + " UTC" }
    var searchText: String { "\(action) \(actor) \(outcome) \(decisionID) \(source)" }
    var json: String {
        let object: [String: Any] = ["entry_id": id, "timestamp": timestamp,
                                     "entry_hash": hash, "previous_hash": previousHash, "data": data]
        guard let bytes = try? JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys]) else { return "" }
        return String(data: bytes, encoding: .utf8) ?? ""
    }
}

