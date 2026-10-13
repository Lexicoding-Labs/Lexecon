import SwiftUI

final class SignInFields: ObservableObject {
    @Published var username = "admin"
    @Published var password = ""
    @Published var newPassword = ""
    @Published var confirmation = ""
}

struct SignInView: View {
    @ObservedObject var model: Workspace
    @StateObject private var fields = SignInFields()

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Image(systemName: "checkmark.shield")
                .font(.system(size: 42, weight: .light)).foregroundStyle(.tint)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 6) {
                Text("Lexecon").font(.largeTitle.bold())
                Text("Local policy and evidence workspace").foregroundStyle(.secondary)
            }
            Form {
                TextField("Username", text: $fields.username)
                    .textContentType(.username)
                    .disabled(model.busy || model.passwordSession != nil)
                SecureField(model.passwordSession == nil ? "Password" : "Current password", text: $fields.password)
                    .textContentType(.password)
                if model.passwordSession != nil {
                    SecureField("New password", text: $fields.newPassword)
                    SecureField("Confirm new password", text: $fields.confirmation)
                }
            }.formStyle(.grouped)
            if let error = model.error { Label(error, systemImage: "exclamationmark.triangle").foregroundStyle(.red).fixedSize(horizontal: false, vertical: true) }
            HStack {
                if model.busy { ProgressView().controlSize(.small) }
                Button("Retry connection") { Task { await model.checkConnection() } }.buttonStyle(.link)
                    .disabled(model.busy)
                if model.passwordSession != nil {
                    Button("Back to Sign In") {
                        fields.password = ""; fields.newPassword = ""; fields.confirmation = ""
                        model.cancelPasswordChange()
                    }.disabled(model.busy)
                }
                Spacer()
                Button(model.passwordSession == nil ? "Sign In" : "Change Password") {
                    if model.passwordSession != nil,
                       fields.newPassword.isEmpty || fields.newPassword != fields.confirmation {
                        model.error = "New passwords must match."
                        return
                    }
                    let old = fields.password; fields.password = ""
                    Task {
                        if model.passwordSession != nil {
                            await model.changePassword(old: old, new: fields.newPassword, username: fields.username)
                            fields.newPassword = ""; fields.confirmation = ""
                        } else { await model.signIn(username: fields.username, password: old) }
                    }
                }.buttonStyle(.borderedProminent).disabled(model.busy || fields.username.isEmpty || fields.password.isEmpty)
            }
            Text("The API runs only on this Mac at 127.0.0.1:8000. Keep the launcher terminal open.")
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding(40).frame(width: 440)
    }
}

