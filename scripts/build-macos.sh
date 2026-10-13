#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
APP="$ROOT/macos/dist/Lexecon.app"
SWIFT_CACHE="${TMPDIR:-/tmp}/lexecon-swift-cache"
CLANG_CACHE="${TMPDIR:-/tmp}/lexecon-clang-cache"

case "${1:-}" in
    ""|--check) ;;
    *) echo "Usage: scripts/build-macos.sh [--check]" >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then
    echo "Usage: scripts/build-macos.sh [--check]" >&2
    exit 2
fi
if [ "$(uname -s)" != Darwin ]; then
    echo "Building Lexecon.app requires macOS and Apple developer tools." >&2
    exit 1
fi
if ! command -v xcrun >/dev/null 2>&1; then
    echo "Apple developer tools with Swift 6.2+ and the macOS 26+ SDK are required. Install a compatible Xcode or Command Line Tools release." >&2
    exit 1
fi
SDK_VERSION=$(xcrun --sdk macosx --show-sdk-version) || {
    echo "Cannot locate the selected macOS SDK. Install/select Apple developer tools with the macOS 26+ SDK." >&2
    exit 1
}
SDK_MAJOR=${SDK_VERSION%%.*}
case "$SDK_MAJOR" in
    ""|*[!0-9]*) echo "Cannot determine the selected macOS SDK version: $SDK_VERSION" >&2; exit 1 ;;
esac
if [ "$SDK_MAJOR" -lt 26 ]; then
    echo "Selected macOS SDK $SDK_VERSION is too old to compile Liquid Glass. Building requires macOS 26+ SDK and Swift 6.2+; the built app still targets macOS 14+. Install/select a compatible Xcode or Command Line Tools release." >&2
    exit 1
fi
SDK_PATH=$(xcrun --sdk macosx --show-sdk-path)
SWIFTC=$(xcrun --sdk macosx --find swiftc)
SWIFT_VERSION=$("$SWIFTC" --version 2>&1 | sed -n 's/.*Swift version \([0-9][0-9]*\.[0-9][0-9]*\).*/\1/p')
case "$SWIFT_VERSION" in
    ""|*[!0-9.]*) echo "Cannot determine the selected Apple Swift compiler version." >&2; exit 1 ;;
esac
SWIFT_MAJOR=${SWIFT_VERSION%%.*}
SWIFT_MINOR=${SWIFT_VERSION#*.}
if [ "$SWIFT_MAJOR" -lt 6 ] || { [ "$SWIFT_MAJOR" -eq 6 ] && [ "$SWIFT_MINOR" -lt 2 ]; }; then
    echo "Selected Swift $SWIFT_VERSION is too old. Install/select Apple developer tools with Swift 6.2+ and the macOS 26+ SDK." >&2
    exit 1
fi
if ! command -v codesign >/dev/null 2>&1; then
    echo "The macOS codesign tool is required to prepare the local app bundle." >&2
    exit 1
fi
ARCH=$(uname -m)
case "$ARCH" in
    arm64|x86_64) ;;
    *) echo "Unsupported Mac architecture: $ARCH" >&2; exit 1 ;;
esac
if [ "${1:-}" = --check ]; then
    echo "Build requirements ready: Swift $SWIFT_VERSION, macOS SDK $SDK_VERSION, $ARCH (deployment target macOS 14+)."
    exit 0
fi
mkdir -p "$APP/Contents/MacOS" "$SWIFT_CACHE" "$CLANG_CACHE"
cp "$ROOT/macos/Lexecon/Info.plist" "$APP/Contents/Info.plist"
CLANG_MODULE_CACHE_PATH="$CLANG_CACHE" SWIFT_MODULE_CACHE_PATH="$SWIFT_CACHE" \
    "$SWIFTC" -sdk "$SDK_PATH" -parse-as-library -module-cache-path "$SWIFT_CACHE" \
    -module-name Lexecon -target "$ARCH-apple-macosx14.0" \
    "$ROOT"/macos/Lexecon/App/*.swift \
    "$ROOT"/macos/Lexecon/Models/*.swift \
    "$ROOT"/macos/Lexecon/Services/*.swift \
    "$ROOT"/macos/Lexecon/Stores/*.swift \
    "$ROOT"/macos/Lexecon/Views/*.swift -o "$APP/Contents/MacOS/Lexecon"
codesign --force --deep --sign - "$APP"
echo "Built $APP"
