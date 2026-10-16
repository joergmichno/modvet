---
name: package-manager
description: Always pnpm, never npm or yarn
metadata:
  originSessionId: 3f1c2a10-6b1e-4c2a-9d1e-0a1b2c3d4e01
  type: feedback
---
Always use pnpm to install or run scripts. Never npm or yarn.
**Why:** the lockfile is pnpm-lock.yaml; an npm install in February committed a package-lock.json and broke CI twice.
**How to apply:** `pnpm add`, `pnpm test`, `pnpm dlx`. If a package-lock.json appears, delete it.
