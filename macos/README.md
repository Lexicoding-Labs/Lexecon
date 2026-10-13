# Lexecon for macOS

The native SwiftUI app uses the existing local FastAPI service. It is a source build for personal review, not a signed or notarized distributable. The app does not bundle Python or run the API inside its own process.

## Run

Building from source requires a Mac with Apple developer tools containing **Swift 6.2+ and the macOS 26+ SDK**, plus Python 3.9+ and `uv`. Use a compatible Xcode or Command Line Tools release; installing the older tools offered on macOS 14–15 is insufficient to compile Liquid Glass. The compiled app's deployment target remains **macOS 14+**, with standard controls on older systems.

Check the selected build tools without installing dependencies, creating an account, or starting the API:

```sh
scripts/build-macos.sh --check
```

Then, from the repository root:

```sh
python3 scripts/start-macos.py
```

The launcher validates the selected tools and builds `macos/dist/Lexecon.app` before account setup. It reconciles the Python environment with `uv.lock` on every launch, including when a previous environment exists; cached, unchanged dependencies need no reinstall. Dependency changes may require network access. Only after those checks succeed does first run prompt for a local administrator password and create ignored `.lexecon/` data. Later runs reuse that data. The launcher then starts the API on `127.0.0.1:8000` and opens the app. Keep the terminal open. Press Ctrl+C to stop the API. To build without starting the service, run `scripts/build-macos.sh`; to start without opening the app, add `--no-browser` to the launcher.

The app holds its bearer session in memory using an ephemeral URL session. It sends requests only to `127.0.0.1:8000` with tenant `default`. The local API supports one shared organization; there is no cloud account or automatic interception of external tool calls.

## Flow

1. Sign in as the local administrator. If prompted for a password change, complete it in the sign-in window.
2. The **Decisions** dashboard opens with an inline **Run policy example** card. The app checks admin identity and asks before replacing a loaded policy in memory.
3. Run the example. It requests a permitted `read` and denied `delete` with `safe_demo`, then compares each response with its ledger entry. No tool executes.
4. Search or filter the newest 200 decisions, then choose a row to inspect its evidence. Timeline and Analytics show other views of those loaded records. Refresh loads the latest page.
5. Select **Verify Integrity** for the full source-ledger integrity check. **Export Audit** saves a ZIP; run `.venv/bin/python scripts/verify-evidence-zip.py /path/to/lexecon-evidence.zip` to rehash the saved package. ZIP rehashing alone does not prove signer identity or the whole source chain.

Refresh, a new example, or a verification attempt clears the previous chain result immediately, including in an open detail view. If the request fails, the app shows the error and leaves the chain **Not checked**; existing decision records remain available.

## Design decisions

The app preserves the original browser dashboard's product flow: Decisions heading and main actions, compact ledger status, an inline guided example, Ledger/Timeline/Analytics/Exports tabs, filters, and full-width decision rows. Selecting a row opens its evidence on demand. Native window controls, account menu, dialogs, keyboard shortcuts (⌘R refresh, ⇧⌘V chain check), SF Symbols, and adaptive appearance supply the Mac interaction patterns.

The design keeps the example, its resulting decisions, verification, and export in one workspace. The forest-green identity, quiet solid cards, and dashboard hierarchy come from the original UI. System typography and native controls add Mac behavior without replacing that hierarchy with a file browser. A Mac build currently requires local Swift Command Line Tools and is verified with `swiftc`; a full Xcode archive, notarization, and broader accessibility testing have not been performed.

Liquid Glass accents Verify Integrity and Export Audit on macOS 26 and later, alongside native window controls. The dashboard canvas, example card, decision rows, and evidence text stay solid. Reduce Transparency uses standard bordered action buttons. macOS 14–15 also use their standard button styles. There is no sidebar or permanent inspector column.

Swift sources are organized under `App`, `Views`, `Models`, `Stores`, and `Services`; the smoke test entrypoint lives under `macos/Tests`. The existing `scripts/start-macos.py` remains the build-and-run entrypoint.
