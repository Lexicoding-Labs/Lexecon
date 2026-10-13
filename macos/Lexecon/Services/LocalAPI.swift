import Foundation

private let apiBase = URL(string: "http://127.0.0.1:8000")!

struct APIError: LocalizedError {
    let message: String
    let statusCode: Int?
    init(message: String, statusCode: Int? = nil) {
        self.message = message
        self.statusCode = statusCode
    }
    var errorDescription: String? { message }
}

final class LocalAPI {
    private let session: URLSession
    var token: String?

    init(session: URLSession? = nil) {
        if let session { self.session = session; return }
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 20
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        self.session = URLSession(configuration: configuration)
    }

    func request(_ path: String, method: String = "GET", body: [String: Any]? = nil, token override: String? = nil) async throws -> Data {
        guard let url = URL(string: path, relativeTo: apiBase)?.absoluteURL,
              url.host == "127.0.0.1", url.port == 8000 else {
            throw APIError(message: "Invalid local API address.")
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("default", forHTTPHeaderField: "X-Tenant-ID")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token = override ?? token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let body {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let data: Data
        let response: URLResponse
        do { (data, response) = try await session.data(for: request) }
        catch {
            throw APIError(message: "Cannot reach the Lexecon API. Start it with python3 scripts/start-macos.py, then retry.")
        }
        guard let http = response as? HTTPURLResponse else { throw APIError(message: "Invalid API response.") }
        guard (200..<300).contains(http.statusCode) else {
            let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
            let detail = json?["detail"] as? String ?? json?["error"] as? String
            throw APIError(message: detail ?? "API request failed (HTTP \(http.statusCode)).", statusCode: http.statusCode)
        }
        return data
    }

    func json(_ path: String, method: String = "GET", body: [String: Any]? = nil, token: String? = nil) async throws -> [String: Any] {
        let data = try await request(path, method: method, body: body, token: token)
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw APIError(message: "The API returned an unexpected response.")
        }
        return json
    }
}

