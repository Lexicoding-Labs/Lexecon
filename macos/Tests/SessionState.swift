// In-memory transport regressions. No server, account, password database or socket.
#if LEXECON_SMOKE
import Foundation

final class MemoryTransport: URLProtocol {
    private static let lock = NSLock()
    private static var currentMode = "ok"
    private static var paths: [String] = []
    private static var logoutHeader: String?
    private var work: DispatchWorkItem?

    static func reset(_ mode: String) {
        lock.lock(); defer { lock.unlock() }
        currentMode = mode; paths = []; logoutHeader = nil
    }
    static var requestCount: Int { lock.lock(); defer { lock.unlock() }; return paths.count }
    static var logoutAuthorization: String? { lock.lock(); defer { lock.unlock() }; return logoutHeader }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        let path = request.url!.path
        Self.lock.lock()
        let mode = Self.currentMode
        Self.paths.append(path)
        if path == "/auth/logout" { Self.logoutHeader = request.value(forHTTPHeaderField: "Authorization") }
        Self.lock.unlock()
        var status = 200
        var json: [String: Any] = [:]
        if path == "/auth/login" {
            if mode == "bad-login" { status = 401; json = ["detail": "Invalid username or password"] }
            else if mode == "restricted" {
                json = ["success": false, "session_id": "in-memory-restricted", "error": "Password change required"]
            } else {
                json = ["success": true, "session_id": "in-memory-session", "user": ["username": "fixture", "role": "admin"]]
            }
        } else if mode == "expired" {
            status = 401; json = ["detail": "Session expired"]
        } else if mode == "unavailable" {
            status = 503; json = ["detail": "Service unavailable"]
        } else if path == "/ledger/entries" {
            json = ["total": 1, "entries": [["entry_id": "fixture-entry", "data": ["decision": "permit"]]]]
        } else if path == "/ledger/verify" { json = ["valid": true] }
        else if path == "/auth/logout" { json = ["success": true] }
        else { status = 404; json = ["detail": "Unconfigured in-memory request"] }
        let data = try! JSONSerialization.data(withJSONObject: json)
        let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!
        let delivery = DispatchWorkItem { [weak self] in
            guard let self else { return }
            self.client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            self.client?.urlProtocol(self, didLoad: data)
            self.client?.urlProtocolDidFinishLoading(self)
        }
        work = delivery
        DispatchQueue.global().asyncAfter(deadline: .now() + (path == "/auth/logout" ? 0.3 : 0), execute: delivery)
    }
    override func stopLoading() { work?.cancel() }
}

@main struct SessionStateTests {
    @MainActor static func workspace() -> Workspace {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [MemoryTransport.self]
        return Workspace(api: LocalAPI(session: URLSession(configuration: configuration)))
    }

    @MainActor static func signIn(_ model: Workspace) async {
        await model.signIn(username: "fixture", password: "in-memory-input")
        require(model.signedIn && model.records.count == 1, "fixture sign-in failed")
        model.chainStatus = "Chain verified"
        model.note = "Earlier evidence"
        model.exportData = Data([0x50, 0x4b])
        model.showingExporter = true
        model.confirmReplacement = true
    }

    @MainActor static func requireCleared(_ model: Workspace) {
        require(!model.signedIn && model.username.isEmpty && model.role.isEmpty, "identity retained")
        require(model.records.isEmpty && model.selectedID == nil, "records retained")
        require(model.exportData == nil && !model.showingExporter, "export retained")
        require(model.passwordSession == nil && !model.confirmReplacement, "pending action retained")
        require(model.chainStatus == "Not checked" && model.note == nil, "verification retained")
    }

    @MainActor static func main() async {
        for operation in ["refresh", "verify", "export"] {
            MemoryTransport.reset("ok")
            let model = workspace()
            await signIn(model)
            MemoryTransport.reset("expired")
            switch operation {
            case "refresh": await model.refresh()
            case "verify": await model.verifyChain()
            default: await model.export()
            }
            requireCleared(model)
            require(model.error?.contains("Sign in again") == true && !model.busy, "missing reauthentication recovery")
        }

        MemoryTransport.reset("ok")
        let logout = workspace()
        await signIn(logout)
        let task = Task { await logout.signOut() }
        try? await Task.sleep(nanoseconds: 80_000_000)
        requireCleared(logout)
        require(logout.busy, "logout should serialize its pending revocation")
        let count = MemoryTransport.requestCount
        await logout.refresh(); await logout.verifyChain(); await logout.export()
        await logout.signIn(username: "fixture", password: "in-memory-input")
        require(MemoryTransport.requestCount == count, "requests overlapped logout")
        await task.value
        requireCleared(logout)
        require(!logout.busy && MemoryTransport.logoutAuthorization == "Bearer in-memory-session", "logout lost its original authorization")
        await signIn(logout)

        MemoryTransport.reset("restricted")
        let expiredChange = workspace()
        await expiredChange.signIn(username: "fixture", password: "in-memory-input")
        require(expiredChange.passwordSession != nil && !expiredChange.signedIn, "missing restricted flow")
        MemoryTransport.reset("expired")
        await expiredChange.changePassword(old: "in-memory-input", new: "in-memory-replacement", username: "fixture")
        requireCleared(expiredChange)
        require(expiredChange.error?.contains("Sign in again") == true, "password change remains trapped")

        MemoryTransport.reset("restricted")
        let cancelled = workspace()
        await cancelled.signIn(username: "fixture", password: "in-memory-input")
        let beforeCancel = MemoryTransport.requestCount
        cancelled.cancelPasswordChange()
        requireCleared(cancelled)
        require(MemoryTransport.requestCount == beforeCancel, "cancel unexpectedly contacted service")

        MemoryTransport.reset("bad-login")
        let invalid = workspace()
        await invalid.signIn(username: "fixture", password: "in-memory-input")
        require(invalid.error == "Invalid username or password", "ordinary login error misclassified as expiry")

        MemoryTransport.reset("ok")
        let unavailable = workspace()
        await signIn(unavailable)
        MemoryTransport.reset("unavailable")
        await unavailable.verifyChain()
        require(unavailable.signedIn && unavailable.records.count == 1, "503 incorrectly signed user out")
        require(unavailable.chainStatus == "Not checked" && unavailable.note == nil, "503 retained verified evidence")
        print("8 native session regressions passed using in-memory responses only")
    }

    static func require(_ condition: Bool, _ message: String) {
        if !condition { fputs("Session regression failed: \(message)\n", stderr); exit(1) }
    }
}
#endif
