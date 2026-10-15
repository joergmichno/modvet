# ModVet

**Vet your Claude Code mods before you install them — deterministic, offline, in milliseconds.**

Mods run unsandboxed inside the agent process with your full permissions. ModVet scans a mod directory for prompt-injection patterns, dangerous capabilities (shell exec, exfiltration, env/file access, permission-lift hooks) and hardcoded secrets — no cloud, no LLM, no account. Findings with `file:line`, JSON or human output, CI-ready exit codes.

```
modvet scan ./my-mod            # Pre-Install-Check
modvet snapshot ./my-mod        # Baseline nach sauberer Installation
modvet diff ./my-mod --against .modvet-snapshot.json   # "The update is the attack"
```

Exit codes: `0` clean · `1` findings ≥ `--fail-on` (default HIGH) · `2` usage error.

## Install (dev)

```
uv pip install -e .
# oder: python -m modvet.cli scan ./some-mod
```

## What it checks

- **Prompt Injection / Instruction Override** (EN+DE, 236 deterministische Pattern, inkl. Homoglyph-/Base64-/Zero-Width-Normalisierung)
- **Capabilities:** Shell-Pipe-Downloads, Base64-Exec, Reverse Shells, Hook-Permission-Lift, Process-Exec, HTTP-POST-Exfil-Pfade, Config-Rewrites, Env-/File-Zugriff
- **Update-Drift:** `snapshot` + `diff` — re-audits nur das Delta nach jedem Mod-Update

## Status

v0.1 — Pre-Release. Woche 1 des ModVet-Build-Plans (`specs/spec-modvet-v0.1.md`). API kann sich ändern.

(C) 2026 Jörg Michno. Engine portiert aus ClawGuard v0.5.0.
