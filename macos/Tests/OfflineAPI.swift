import Foundation
struct APIError: LocalizedError {
    let message: String
    let statusCode: Int? = nil
    var errorDescription: String? { message }
}
final class LocalAPI {
    var token: String?
    func request(_ path: String, method: String = "GET", body: [String: Any]? = nil, token: String? = nil) async throws -> Data {
        throw APIError(message: "This visual preview has no API connection. Run the actual Lexecon app to use this action.")
    }
    func json(_ path: String, method: String = "GET", body: [String: Any]? = nil, token: String? = nil) async throws -> [String: Any] {
        throw APIError(message: "This visual preview has no API connection. Run the actual Lexecon app to use this action.")
    }
}
