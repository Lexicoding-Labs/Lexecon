import SwiftUI

@MainActor final class Workspace: ObservableObject {
    @Published var username = ""
    @Published var role = ""
    @Published var records: [DecisionRecord] = []
    @Published var selectedID: String?
    @Published var busy = false
    @Published var error: String?
    @Published var note: String?
    @Published var chainStatus = "Not checked"
    @Published var passwordSession: String?
    @Published var confirmReplacement = false
    @Published var exportData: Data?
    @Published var showingExporter = false

    private let api: LocalAPI
    init(api: LocalAPI = LocalAPI()) { self.api = api }
    var signedIn: Bool { api.token != nil && !username.isEmpty }
    var selectedRecord: DecisionRecord? { records.first { $0.id == selectedID } }

    func signIn(username: String, password: String) async {
        await perform {
            let response = try await api.json("/auth/login", method: "POST", body: ["username": username.trimmingCharacters(in: .whitespacesAndNewlines), "password": password])
            if response["success"] as? Bool != true {
                if let session = response["session_id"] as? String { passwordSession = session }
                throw APIError(message: response["error"] as? String ?? "Sign in failed.")
            }
            guard let token = response["session_id"] as? String,
                  let user = response["user"] as? [String: Any] else { throw APIError(message: "Sign in returned no session.") }
            api.token = token
            self.username = user["username"] as? String ?? username
            role = user["role"] as? String ?? ""
            passwordSession = nil
            try await fetchRecords()
        }
    }

    func changePassword(old: String, new: String, username: String) async {
        guard let session = passwordSession else { return }
        await perform {
            let response = try await api.json("/auth/change-password", method: "POST", body: ["old_password": old, "new_password": new], token: session)
            guard response["success"] as? Bool == true else { throw APIError(message: "Password change failed.") }
            passwordSession = nil
        }
        if error == nil { await signIn(username: username, password: new) }
    }

    func checkConnection() async {
        await perform { _ = try await api.json("/health"); note = "Local API is ready." }
    }

    func refresh() async { await perform { try await fetchRecords(); note = "Decisions refreshed." } }

    private func invalidateVerification() {
        chainStatus = "Not checked"
        note = nil
    }

    private func fetchRecords() async throws {
        invalidateVerification()
        // The API returns oldest first. Locate the final page before reversing it.
        var response = try await api.json("/ledger/entries?event_type=decision&limit=200")
        guard let total = response["total"] as? Int, total >= 0 else {
            throw APIError(message: "The API returned an invalid decision count. Refresh to retry.")
        }
        if total > 200 {
            response = try await api.json("/ledger/entries?event_type=decision&limit=200&offset=\(total - 200)")
        }
        records = ((response["entries"] as? [Any]) ?? []).compactMap(DecisionRecord.init).reversed()
        if selectedID == nil || !records.contains(where: { $0.id == selectedID }) { selectedID = records.first?.id }
    }

    func verifyChain() async {
        await perform {
            // Clear prior evidence before awaiting: failures must never retain success.
            invalidateVerification()
            let response = try await api.json("/ledger/verify")
            let valid = response["valid"] as? Bool ?? false
            chainStatus = valid ? "Chain verified" : "Chain failed verification"
            note = valid ? "Source ledger chain verified at this point in time." : "The source ledger failed verification. Inspect the API report before trusting an export."
        }
    }

    func prepareExample() async {
        var readyToRun = false
        await perform {
            let identity = try await api.json("/auth/me")
            let user = identity["user"] as? [String: Any] ?? [:]
            guard user["role"] as? String == "admin" else { throw APIError(message: "Only a local administrator can load the example policy.") }
            let policy = try await api.json("/policies")
            let count = (policy["terms_count"] as? Int ?? 0) + (policy["relations_count"] as? Int ?? 0)
            if count > 0 { confirmReplacement = true }
            else { readyToRun = true }
        }
        if readyToRun { await runExample() }
    }

    func runExample() async {
        await perform {
            invalidateVerification()
            let actor = username
            let relations: [[String: String]] = [
                ["type": "permits", "subject": "actor:\(actor)", "action": "action:read"],
                ["type": "permits", "subject": "actor:\(actor)", "action": "tool:safe_demo"]
            ]
            _ = try await api.json("/policies/load", method: "POST", body: ["policy": ["relations": relations]])
            var outcomes: [String] = []
            for (action, expected) in [("read", "permit"), ("delete", "deny")] {
                let request: [String: Any] = ["actor": actor, "tool": "safe_demo", "user_intent": "Local guided policy example", "context": ["demo": true], "proposed_action": action]
                let decision = try await api.json("/decide", method: "POST", body: request)
                let check = try await api.json("/decide/verify", method: "POST", body: decision)
                guard decision["decision"] as? String == expected, check["verified"] as? Bool == true else {
                    throw APIError(message: "Unexpected result or response-to-ledger comparison for \(action). Inspect the loaded policy and decision records.")
                }
                outcomes.append("\(action): \(expected)")
            }
            try await fetchRecords()
            note = "\(outcomes.joined(separator: " · ")). Both responses matched ledger records. No tool ran. Check the full chain separately."
        }
    }

    func export() async {
        await perform {
            let bytes = try await api.request("/evidence/export", method: "POST", body: ["include_verification": true])
            guard bytes.starts(with: [0x50, 0x4b]) else { throw APIError(message: "Export did not return a ZIP archive.") }
            exportData = bytes
            showingExporter = true
        }
    }

    func signOut() async {
        await perform {
            let token = api.token
            clearSession()
            // Clear local evidence immediately and serialize logout with other operations.
            if let token { _ = try? await api.json("/auth/logout", method: "POST", token: token) }
        }
    }

    func cancelPasswordChange() {
        guard !busy else { return }
        clearSession()
    }

    private func clearSession() {
        api.token = nil
        username = ""; role = ""; records = []; selectedID = nil
        passwordSession = nil; chainStatus = "Not checked"; note = nil; error = nil
        confirmReplacement = false; exportData = nil; showingExporter = false
    }

    private func perform(_ operation: () async throws -> Void) async {
        guard !busy else { return }
        busy = true; error = nil
        defer { busy = false }
        do { try await operation() }
        catch {
            if let failure = error as? APIError, failure.statusCode == 401,
               api.token != nil || passwordSession != nil {
                clearSession()
                self.error = "Your session expired or was revoked. Sign in again."
            } else {
                self.error = error.localizedDescription
            }
        }
    }
}

