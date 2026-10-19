# ModVet

**Vet your Claude Code mods before you install them — deterministic, offline, in milliseconds.**

Mods run unsandboxed inside the agent process with your full permissions. ModVet scans a mod directory for prompt-injection patterns, dangerous capabilities (shell exec, exfiltration, env/file access, permission-lift hooks, update trojans) and hardcoded secrets — no cloud, no LLM, no account. Findings with `file:line`, OWASP MCP Top 10 mapping, JSON/SARIF/human output, CI-ready exit codes.

```
modvet scan ./my-mod                    # Pre-Install-Check (human output)
modvet scan ./my-mod --json             # machine-readable report
modvet scan ./my-mod --format sarif     # GitHub Code Scanning kompatibel
modvet badge --input report.json        # Status-Badge als SVG
modvet snapshot ./my-mod                # Baseline nach sauberer Installation
modvet diff ./my-mod --against .modvet-snapshot.json   # "The update is the attack"
```

Exit codes: `0` clean · `1` findings ≥ `--fail-on` (default HIGH) · `2` usage error.

## Install

```
pip install modvet
```

Requires Python ≥ 3.9, zero dependencies. Development: `uv pip install -e .`

## What it checks

- **Prompt Injection / Instruction Override** (EN + DE, ~400 deterministische Pattern inkl. Homoglyph-/Leet-/Base64-/Zero-Width-/Reverse-Normalisierung)
- **Capability-Kombinationslogik:** Einzel-Capabilities (fetch, process.env, fs) sind normale Mod-Arbeit — erst KOMBINATIONEN im selben Ausdruck (Env-Read + POST, Exec + Fetch) werden gemeldet. Plus Angriffsprimitive: Shell-Pipe-Downloads, Base64-Exec, Reverse Shells, Hook-Permission-Lift, Config-Rewrite, Committed-Env-Files, npm-Lifecycle-Skripte.
- **Mod-spezifische Detektoren (v0.2):** Prompt-Compose-Rewrite, PreToolUse-Argument-Rewrite, Update-Delta-Trojan.
- **OWASP MCP Top 10 Mapping:** jedes Finding trägt seine MCP01–MCP10-Referenz (JSON-Feld `owasp_mcp`).
- **Update-Drift:** `snapshot` + `diff` — re-audits nur das Delta nach jedem Mod-Update. Der Update-Mechanismus selbst ist ein Angriffspfad: „the update is the attack".

## Vergleichstabelle (Stand 10/2026)

| | **ModVet** | Snyk (MCP/Skills-Scan) | mcp-triage |
|---|---|---|---|
| Fokus | Claude-Code-Mods (+ Skills) | MCP-Server/Skills, breites DevSecOps | MCP-Server-Review |
| Betrieb | **lokal & offline**, 0 €, kein Konto | Cloud-Konto, SaaS-Pricing | lokal/Repos |
| Verfahren | deterministisch, keine LLM-Entscheidungen | Hybrid (inkl. proprietäre Analyse) | Review-basiert |
| Update-Delta | **`snapshot`/`diff` re-auditiert nur Deltas** | Neuer Voll-Scan je Version | — |
| OWASP-Mapping | MCP Top 10 im Finding-Feld | vorhanden | — |
| Output | JSON, SARIF, Badge-SVG | SaaS-UI/API | Markdown |
| Transparenz | jede Regel im Open Source einsehbar | teilweise proprietär | Open Source |

## Benchmark

12 echte Mod-Repos (awesome-claude-code-Katalog): FP-Reduktion von 1.815 auf <300 Findings (−85 %) seit der v0.1-Engine — Details in `specs/benchmark-results.md` und `specs/pattern-audit.md`.

## Status

v0.2.2 — live on PyPI (`pip install modvet`). Phase 2 (Outputs/Verteilung) abgeschlossen: SARIF, Badge, OWASP-Mapping. Nächste Schritte: SKILL.md-/MCP-Scanning (Fast-Follow), Pro-/Audit-Angebot nach Traktion.

(C) 2026 Jörg Michno. Engine portiert aus ClawGuard v0.5.0.
