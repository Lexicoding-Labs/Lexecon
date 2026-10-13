#!/usr/bin/env python3
"""Owner-operated launch of the required-gate Hermes pilot; may make model calls."""

import argparse
import importlib
import sys
from pathlib import Path

from required_runtime import initialize_required_runtime


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--hermes-checkout", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        initialize_required_runtime(args.home, args.hermes_checkout)
    except Exception:
        print("Required-gate startup refused. Check the isolated profile and patched candidate; no model was started.")
        return 1
    sys.argv = ["hermes", "chat"]
    return importlib.import_module("hermes_cli.main").main()


if __name__ == "__main__":
    raise SystemExit(main())
