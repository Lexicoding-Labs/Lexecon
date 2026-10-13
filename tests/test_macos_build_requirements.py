"""Check shell preflight using synthetic tools; never compile or create accounts."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build-macos.sh"


@pytest.fixture
def toolchain(tmp_path):
    tools = tmp_path / "tools"
    tools.mkdir()
    scripts = {
        "uname": '#!/bin/sh\nif [ "$1" = -s ]; then echo Darwin; else echo arm64; fi\n',
        "swiftc": '#!/bin/sh\necho "Apple Swift version ${TEST_SWIFT_VERSION}"\n',
        "codesign": "#!/bin/sh\nexit 0\n",
        "xcrun": '''#!/bin/sh
case "$3" in
  --show-sdk-version) echo "$TEST_SDK_VERSION" ;;
  --show-sdk-path) echo /synthetic/sdk ;;
  --find) echo "$TEST_TOOLS/swiftc" ;;
  *) exit 1 ;;
esac
''',
    }
    for name, contents in scripts.items():
        path = tools / name
        path.write_text(contents)
        path.chmod(0o700)
    return {
        **os.environ, "PATH": f"{tools}:/usr/bin:/bin", "TEST_TOOLS": str(tools),
        "TEST_SDK_VERSION": "26.0", "TEST_SWIFT_VERSION": "6.2",
    }


@pytest.mark.parametrize(("sdk", "swift", "success", "message"), [
    ("15.5", "6.1", False, "too old to compile Liquid Glass"),
    ("26.0", "6.1", False, "Selected Swift 6.1 is too old"),
    ("unknown", "6.2", False, "Cannot determine the selected macOS SDK"),
    ("26.0", "6.2", True, "Build requirements ready"),
    ("27.0", "6.4", True, "Build requirements ready"),
])
def test_toolchain_requirements_are_separate_from_deployment_target(toolchain, sdk, swift, success, message):
    toolchain.update(TEST_SDK_VERSION=sdk, TEST_SWIFT_VERSION=swift)
    result = subprocess.run(["/bin/sh", str(SCRIPT), "--check"], env=toolchain, capture_output=True, text=True)
    assert (result.returncode == 0) is success
    assert message in result.stdout + result.stderr
    if success:
        assert "deployment target macOS 14+" in result.stdout


def test_check_does_not_build_or_create_cache_directories(toolchain, tmp_path):
    # If check mode accidentally calls the compiler for more than its version,
    # this fake compiler exits nonzero and makes the test fail.
    swift = Path(toolchain["TEST_TOOLS"]) / "swiftc"
    swift.write_text('#!/bin/sh\n[ "$1" = --version ] || exit 91\necho "Apple Swift version 6.2"\n')
    cache = tmp_path / "unused-cache-root"
    toolchain["TMPDIR"] = str(cache)
    result = subprocess.run(["/bin/sh", str(SCRIPT), "--check"], env=toolchain, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert not cache.exists()
