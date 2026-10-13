// Compiled only by tests/test_macos_smoke.py against a disposable loopback API.
#if LEXECON_SMOKE
import Foundation

@main struct LexeconSmoke {
    @MainActor static func main() async {
        let workspace = Workspace()
        let scenario = CommandLine.arguments.dropFirst().first ?? "flow"
        let environment = ProcessInfo.processInfo.environment
        await workspace.signIn(username: environment["LEXECON_TEST_USERNAME"] ?? "admin",
                               password: environment["LEXECON_TEST_PASSWORD"] ?? "test-only")
        guard workspace.signedIn, workspace.error == nil else { fail("sign in: \(workspace.error ?? "unknown")") }
        if scenario.contains("failure") {
            await checkFailure(workspace, refreshing: scenario.hasPrefix("refresh"))
            return
        }
        let paged = scenario == "paging" || scenario == "live"
        if paged {
            guard workspace.records.count == 200,
                  workspace.records.first?.decisionID == "seed-200",
                  workspace.records.last?.decisionID == "seed-1" else { fail("initial newest page") }
        }
        await workspace.prepareExample()
        guard workspace.confirmReplacement, workspace.records.count == (paged ? 200 : 0) else {
            fail("existing policy should require confirmation before any decisions")
        }
        await workspace.runExample() // The user's confirmation action in this disposable test.
        guard workspace.error == nil, workspace.records.count == (paged ? 200 : 2),
              workspace.records.prefix(2).map(\.outcome) == ["deny", "permit"] else {
            fail("example: \(workspace.error ?? "unexpected records")")
        }
        if paged {
            guard workspace.records.last?.decisionID == "seed-3" else { fail("new examples must advance the newest page") }
        }
        await workspace.verifyChain()
        guard workspace.chainStatus == "Chain verified" else { fail("ledger chain: \(workspace.error ?? workspace.chainStatus)") }
        await workspace.export()
        guard workspace.showingExporter, workspace.exportData?.starts(with: [0x50, 0x4b]) == true else {
            fail("export: \(workspace.error ?? "missing ZIP")")
        }
        if let path = environment["LEXECON_TEST_EXPORT"] {
            do { try workspace.exportData!.write(to: URL(fileURLWithPath: path)) }
            catch { fail("save disposable export: \(error)") }
        }
        await workspace.signOut()
        guard !workspace.signedIn else { fail("sign out") }
        print("macOS API flow passed: sign in, permit/deny, response comparison, chain check, ZIP, sign out")
    }

    @MainActor static func checkFailure(_ workspace: Workspace, refreshing: Bool) async {
        guard let record = workspace.records.first else { fail("missing failure fixture") }
        // Keep the same detail instance across success, in-flight request, and failure.
        let detail = DecisionDetail(record: record, model: workspace)
        await workspace.verifyChain()
        guard workspace.chainStatus == "Chain verified", detail.chainStatus == "Chain verified",
              workspace.note != nil else { fail("initial successful verification") }
        let operation = Task {
            if refreshing { await workspace.refresh() } else { await workspace.verifyChain() }
        }
        // The fixture holds the failing request open for 300 ms.
        try? await Task.sleep(nanoseconds: 80_000_000)
        guard workspace.busy, workspace.chainStatus == "Not checked",
              detail.chainStatus == "Not checked", workspace.note == nil else {
            fail("stale success while request is in flight")
        }
        await operation.value
        guard !workspace.busy, workspace.error != nil, workspace.chainStatus == "Not checked",
              detail.chainStatus == "Not checked", workspace.note == nil else {
            fail("stale success after failed request")
        }
        guard workspace.records.count == 1 else { fail("failed refresh lost recorded evidence") }
        print("macOS failure regression passed: store and existing detail invalidated before and after failure")
    }

    static func fail(_ message: String) -> Never {
        fputs("macOS API flow failed: \(message)\n", stderr)
        exit(1)
    }
}
#endif
