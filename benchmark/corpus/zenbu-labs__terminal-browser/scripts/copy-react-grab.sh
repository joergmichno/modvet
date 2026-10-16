#!/bin/bash
# react-grab's browser bundle is read from assets at runtime, in dev and in releases alike
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$(node -e 'console.log(require.resolve("react-grab/dist/index.global.js",{paths:[process.argv[1]]}))' "$ROOT/browser")"
mkdir -p "$ROOT/assets/react-grab"
cp "$SRC" "$ROOT/assets/react-grab/index.global.js"
