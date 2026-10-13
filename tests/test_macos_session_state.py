"""Run native state regressions with URLProtocol; no socket or account creation."""

import shutil
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(sys.platform != "darwin" or not shutil.which("swiftc"), reason="macOS Swift required")
def test_native_session_recovery(tmp_path):
    binary = tmp_path / "LexeconSessionTests"
    sources = sorted((ROOT / "macos/Lexecon").rglob("*.swift"))
    subprocess.run([
        "swiftc", "-parse-as-library", "-DLEXECON_SMOKE", "-module-name", "LexeconSessionTests",
        "-target", f"{platform.machine()}-apple-macosx14.0",
        "-module-cache-path", str(Path(tempfile.gettempdir()) / "lexecon-swift-cache"),
        *map(str, sources), str(ROOT / "macos/Tests/SessionState.swift"), "-o", str(binary),
    ], cwd=ROOT, check=True, timeout=180)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    assert "8 native session regressions passed" in result.stdout
