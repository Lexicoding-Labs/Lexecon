# Lexecon

**A decision you can inspect. A record you can verify.**

Lexecon is a local policy decision and evidence workspace for one organization. Its FastAPI service evaluates an action and requested tool against an in-memory policy, returns a permit or deny, and records a hash-linked decision event in a local SQLite ledger. A browser dashboard and a native macOS app let you inspect decisions, check ledger integrity, and export evidence.

![Lexecon local decision, enforcement, and evidence flow](docs/architecture.svg)

The dashboard's **Run policy example** requests a permitted read and a denied delete, then compares both responses with their ledger entries. It does not execute a tool. The bundled [reference adapter](scripts/reference_tool_adapter.py) separately verifies a short-lived capability grant before one harmless local text transformation. Other tools require their own enforcement adapter. See [architecture and trust boundaries](docs/architecture.md).

## Run the browser dashboard

Requires Python 3.9+, [uv](https://docs.astral.sh/uv/), Node.js, and npm. From the repository root:

```sh
python3 scripts/start-local.py
```

The launcher installs locked dependencies, prompts for a local `admin` password on first run, and starts the API and dashboard on `127.0.0.1`. Open <http://127.0.0.1:3000/login> and sign in. Data is stored in the ignored `.lexecon/` directory; later runs reuse it. Keep the terminal open and press Ctrl+C to stop both servers. Use `--no-browser` to print the URL without opening it.

If your home cache is read-only, give uv and npm writable ignored cache paths:

```sh
UV_CACHE_DIR="$PWD/.lexecon/cache/uv" npm_config_cache="$PWD/.lexecon/cache/npm" \
  python3 scripts/start-local.py --no-browser
```

After signing in, select **Run policy example**, inspect the permitted and denied decisions, select **Verify Integrity**, and open a decision or **Export Audit**. The example asks before replacing an existing in-memory policy. The [local walkthrough](docs/walkthrough.md) describes each check.

## Run the native Mac app

The app targets macOS 14+. Building it requires Apple developer tools with Swift 6.2+ and the macOS 26+ SDK, plus Python 3.9+ and uv. Check the selected tools with `scripts/build-macos.sh --check`, then run:

```sh
python3 scripts/start-macos.py
```

The launcher builds `macos/dist/Lexecon.app`, starts the local API, and opens the app. It prompts for the local administrator password on first run and reuses `.lexecon/` on later runs. The app holds its session in memory. See [Mac build and usage](macos/README.md).

## Verify the tool boundary

The disposable command-line proof creates temporary local data, exercises `/decide` and `/decide/verify`, and has the reference adapter verify a grant before uppercasing `local demo`. It rejects a forged grant and an unapproved tool. It needs no browser, Redis server, cloud account, or live model:

```sh
uv sync --locked --extra dev
.venv/bin/python scripts/demo-proof.py
```

For automated checks, see [contributing](CONTRIBUTING.md). The optional [Hermes integration](integrations/hermes/README.md) provides two bounded, locally gated file tools; it does not connect the Mac app to an agent automatically.

## Scope and limits

Lexecon supports the HTTP tenant `default` as one shared organization. A permit requires policy permission for both the action and requested tool. Capability grants are short-lived and process-bound. The ledger's SHA-256 links detect changes relative to a trusted chain head; [the saved-ZIP verifier](scripts/verify-evidence-zip.py) checks exported file and event hashes. Neither check by itself establishes signer trust or proves that an external tool ran.

This is a local prototype, not a hosted authorization service or compliance certification. Global governance stores do not have verified tenant isolation, HTTP MFA flows are incomplete, and external tools are not automatically gated. Do not deploy it as a public authorization or audit service. See [security scope](SECURITY.md).

MIT licensed. Application source is under [`src/lexecon/`](src/lexecon/); the browser and native clients are under [`frontend/`](frontend/) and [`macos/`](macos/).
