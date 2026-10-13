import SwiftUI
import UniformTypeIdentifiers

struct EvidenceDocument: FileDocument {
    static var readableContentTypes: [UTType] { [.zip] }
    var bytes: Data
    init(bytes: Data) { self.bytes = bytes }
    init(configuration: ReadConfiguration) throws { bytes = configuration.file.regularFileContents ?? Data() }
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper { FileWrapper(regularFileWithContents: bytes) }
}

