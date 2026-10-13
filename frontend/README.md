# Lexecon local dashboard

The React dashboard is the browser view of the supported local, single-organization Lexecon prototype. Start it together with the FastAPI server from the repository root:

```sh
python3 scripts/start-local.py
```

The launcher installs dependencies when needed, initializes an administrator on first run, starts both servers on loopback, and opens <http://127.0.0.1:3000/login>. Sign in as `admin` with the password you chose. If the API is unavailable, the login page shows a local startup instruction and a retry button.

In the dashboard, **Run policy example** loads a small in-memory policy, requests a permitted read and a denied delete through `/decide`, and checks both returned responses with `/decide/verify`. It asks before replacing an already loaded policy. **Verify Integrity** checks the source ledger hash chain; it does not prove that a decision was authorized. A failed recheck clears the previous success. **Export Audit** downloads an evidence ZIP. The decision table, timeline, and outcome counts are based on returned ledger entries. The server records whether an entry came from policy evaluation or the synthetic seed endpoint; the separate caller demo flag is only a display hint. Export history is not presented as a completed feature.

For frontend-only development:

```sh
npm ci
HOST=127.0.0.1 BROWSER=none npm start
```

The API must be available at `http://127.0.0.1:8000`, or configured with `REACT_APP_API_BASE_URL`. The frontend expects the `default` organization. Check the frontend with `npx tsc --noEmit`, `CI=true npm test -- --watch=false --silent`, and `npm run build`. See the [repository README](../README.md) and [portfolio verification notes](../docs/portfolio-verification.md) for scope and evidence.
