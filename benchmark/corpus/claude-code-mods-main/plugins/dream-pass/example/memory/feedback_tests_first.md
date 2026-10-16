---
name: tests-first
description: Write the failing test before the fix
metadata:
  type: feedback
---
For any bug, write a failing test first, then fix it.
**Why:** two regressions in January came back because fixes had no test.
**How to apply:** vitest in `tests/`, run with `pnpm test` (see [[pnpm]]).
