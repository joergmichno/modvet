#!/bin/bash
set -euo pipefail

# .claude/types holds the plugin API declarations the plugin's tsconfig includes.
# They are gitignored and tied to the installed Claude Code, so we regenerate
# them here rather than checking them in. Claude Code writes them via /plugin-types.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$ROOT/claude-code-plugin/.claude/types"

if [ "${1:-}" = "--if-missing" ] && [ -f "$DIR/claude-code.d.ts" ]; then
  exit 0
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "plugin-types: claude is not on PATH, skipping (run 'pnpm types' once it is installed)" >&2
  exit 0
fi

mkdir -p "$DIR"
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude -p "/plugin-types $DIR" \
  || echo "plugin-types: claude could not generate the types, skipping" >&2
