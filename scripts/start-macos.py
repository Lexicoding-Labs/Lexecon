#!/usr/bin/env python3
"""Build Lexecon.app and run its loopback API with the existing local data."""

import os
import sys
from pathlib import Path

if __name__ == "__main__":
    command = [sys.executable, str(Path(__file__).with_name("start-local.py")), "--macos", *sys.argv[1:]]
    os.execv(sys.executable, command)
