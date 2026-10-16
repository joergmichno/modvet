#!/usr/bin/env bash
set -euo pipefail

if ! command -v terminal-browser >/dev/null 2>&1; then
  echo "terminal-browser is not installed — see https://github.com/zenbu-labs/terminal-browser" >&2
  exit 1
fi

exec terminal-browser open --split right
