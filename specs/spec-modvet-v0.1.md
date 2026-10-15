# Spec: ModVet CLI v0.1 (Woche 1)

## Goal
ModVet — deterministischer, lokaler Pre-Install-Scanner für Claude-Code-Mods auf Basis der portierten ClawGuard-Engine (236 Pattern, ~6 ms, offline).

## Was + Warum
Developer installieren Claude-Code-Mods, die unsandboxed im Agentenprozess laufen. ModVet scannt einen Mod vor der Installation auf Prompt-Injection, gefährliche Capabilities, Secrets und Update-Drift — ohne Cloud, ohne LLM, in Millisekunden. Einstiegstor für die ModVet-Produktlinie (Trust-Badges, CI-Gate, Pro-Abo folgen in Woche 2–4).

## Acceptance-Kriterien (fertig heißt:)

- [x] A1 Repo `D:\AI-Labs\modvet` (git init, .gitignore, README mit Pitch + Install + Usage)
- [x] A2 Engine-Port: 236 Pattern aus mapping-patterns.csv + Scanner-Kern als Python-Paket (`modvet/core`), KEINE Laufzeit-Abhängigkeit zum VPS
- [x] A3 CLI `modvet scan <pfad>`: erkennt Mod-Dateien (plugin.json, hooks, .ts/.js/.mjs), meldet Findings mit severity + file:line: (a) Prompt-Injection/Instruction-Override, (b) Capabilities (fetch/env/fs.write/exec/curl|sh/base64-exec/reverse-shell/exfil), (c) Secrets (API-Key-Muster)
- [x] A4 Update-Drift: `modvet snapshot <pfad>` + `modvet diff <pfad> --against <snapshot>` → Hash-Delta + Findings nur im Delta
- [x] A5 Ausgabe JSON-Report + Human-Text; Exitcodes 0=clean, 1=Findings≥fail-on (default: high), 2=usage
- [x] A6 Demo: Scan auf 2 Beispielen (1 echter Mod von GitHub, 1 synthetisch-bösartiger Testmod) — Findings dokumentiert (unten)
- [x] A7 Verification: Tests (stdlib-runner, 4 Tests: clean/malicious/snapshot-diff/usage) grün

## Demo-Ergebnisse (15.10., live)

- **Clean-Fixture:** 0 Findings, Exit 0 ✓
- **Malicious-Fixture (synthetisch):** 9 Findings, CRITICAL, Exit 1 — Direct Override, Env Read, Exfil-POST, Shell-Pipe-Download, Base64-Exec erkannt ✓
- **Echter Mod (hamzafer/claude-code-mods, 254★, Playwright-Browser-Controller):** 43 Findings, CRITICAL — v. a. echtes Capability-Signal (10× Process Exec, 8× File Write, 3× Env Read) ✓
- **FP-Reduktion:** „Command Injection in Output" feuerte auf Doku-Backticks → Refiner (Kommando-Verb-Heuristik) senkte 91→43 Findings. Rest-Rauschen: Mail-Adressen in READMEs (LOW) — dokumentierte Grenze, Woche-1-Polish.

## Non-Goals (Woche 1)
Kein Web-UI · keine Badge-Registry · keine GitHub Action · kein MCP-Server · keine Cloud-API · kein Pro-/Payment · keine LLM-Aufrufe (deterministisch) · keine Publikation/npm-Publish (erst nach Jörg-GO).

## Verification
`modvet scan` auf Demo-Mods liefert JSON-Findings mit Datei/Zeile; Exitcodes 0/1 korrekt; `modvet diff` zeigt nur Delta-Findings; Test-Suite grün.
