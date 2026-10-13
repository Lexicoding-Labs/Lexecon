#!/usr/bin/env python3
"""Build an offline native presentation harness, never the production app.

No API, credentials, keys, authentication, policy execution or verification.
Output is explicitly labeled illustrative and must not be used as test evidence.
"""

import argparse
import json
import os
import plistlib
import signal
import subprocess
import tempfile
import time
from contextlib import suppress
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    """Build the offline harness and capture its own windows without network access."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/showcase/macos")
    parser.add_argument(
        "--scene",
        choices=["01-empty", "02-outcomes", "03-detail", "04-timeline", "05-analytics", "06-exports"],
        help="Capture one named scene only",
    )
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="lexecon-offline-capture-"))
    app = stage / "LexeconWalkthrough.app"
    binary = app / "Contents/MacOS/LexeconWalkthrough"
    binary.parent.mkdir(parents=True)
    (app / "Contents/Info.plist").write_bytes(
        plistlib.dumps(
            {
                "CFBundleExecutable": "LexeconWalkthrough",
                "CFBundleName": "LexeconWalkthrough",
                "CFBundleIdentifier": "local.lexecon.offline-walkthrough",
                "CFBundlePackageType": "APPL",
                "NSPrincipalClass": "NSApplication",
            },
        ),
    )
    subprocess.run(  # noqa: S603 — fixed binaries and authored paths, without a shell.
        [
            "/usr/bin/swiftc",
            "-module-cache-path",
            str(stage / "swift-cache"),
            "-parse-as-library",
            "-DLEXECON_SMOKE",
            *map(str, sorted(p for p in (ROOT / "macos/Lexecon").rglob("*.swift") if p.name != "LocalAPI.swift")),
            str(ROOT / "macos/Tests/OfflineAPI.swift"),
            str(ROOT / "macos/Tests/Walkthrough.swift"),
            "-o",
            str(binary),
        ],
        check=True,
    )
    subprocess.run(  # noqa: S603 — fixed binaries and authored paths, without a shell.
        [
            "/usr/bin/codesign",
            "--force",
            "--sign",
            "-",
            str(app),
        ],
        check=True,
    )
    scenes = (
        [arguments.scene]
        if arguments.scene
        else [
            "01-empty",
            "02-outcomes",
            "03-detail",
            "04-timeline",
            "05-analytics",
            "06-exports",
        ]
    )
    request = stage / "capture-request.json"
    for scene in scenes:
        request.unlink(missing_ok=True)
        subprocess.run(  # noqa: S603 — fixed binaries and authored paths, without a shell.
            [
                "/usr/bin/open",
                "-n",
                str(app),
                "--stdout",
                str(stage / (scene + ".log")),
                "--stderr",
                str(stage / (scene + ".err")),
                "--args",
                scene,
                str(stage),
            ],
            check=True,
        )
        pid = None
        try:
            for _ in range(150):
                if request.exists():
                    state = json.loads(request.read_text())
                    if state["name"] != scene:
                        raise RuntimeError("Unexpected capture state")
                    pid = state["pid"]
                    subprocess.run(  # noqa: S603 — fixed binaries and authored paths, without a shell.
                        [
                            "/usr/sbin/screencapture",
                            "-x",
                            "-o",
                            "-l",
                            str(state["window"]),
                            str(output / (scene + ".png")),
                        ],
                        check=True,
                    )
                    print(f"Captured {scene}: illustrative offline UI, app window only")
                    break
                time.sleep(0.1)
            else:
                raise TimeoutError(f"Capture timed out. Logs: {stage}")
        finally:
            if pid:
                with suppress(ProcessLookupError):
                    os.kill(pid, signal.SIGTERM)
            request.unlink(missing_ok=True)
    print("No authentication, API evaluation, chain verification or export performed.")


if __name__ == "__main__":
    main()
