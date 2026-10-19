# Spec: ModVet v0.2 — Full-Optimization (Engine + Patterns + Verteilung)

> 16.10.2026 · Jörg-Entscheid („Full-Optimierungs-Prozess, da bereits veraltet") · Kosten: 0 €
> Ausgangslage: Gerüst v0.1 (15.10.) frisch, aber Engine-Port = ClawGuard-Kern von ~Juli 2026 (236 Pattern, vor der Mod-Ära entstanden). Veraltung liegt in der ERKENNUNG, nicht im Gerüst.

## Goal
ModVet von einem Port alter ClawGuard-Muster zu einem **mod-zeitgemäßen Scanner** machen: Pattern-Basis am Stand Okt 2026, gemessene FP/TP-Raten statt Bauchgefühl, OWASP-MCP-Mapping, saubere Verteilung.

## Acceptance-Kriterien (fertig heißt:)

- [x] A1 **Pattern-Audit:** alle 236 CSV-Pattern kategorisiert (Prompt-Injection/Command/Social/…), veraltete/irrelevante markiert, Lücken gegen OWASP MCP Top 10 (MCP01–MCP10) + Mod-Vektoren (hooks/register.ts, prompt.compose, tool-call-rewriting, update-drift) dokumentiert → `specs/pattern-audit.md` (19.10.)
- [x] A2 **Benchmark-Corpus:** ≥20 echte Mods lokal gespiegelt (22 Ordner, 10 neue per Scout-Kind 18.10., verifiziert); Mess-Skript `tools/benchmark.py` mit Datei-Cap (--max-files 500, [CAP]-Markierung) — je Mod: Findings, Laufzeit, Risiko → `benchmark/results.json` + `specs/benchmark-results.md` (19.10.)
- [~] A3 **FP-Quote gesenkt:** Alt-Corpus (12 Repos) 1.815 → ~272 Findings (−85 %), 1 CLEAN, 7 HIGH — praktisch erreicht. Voll-Corpus (22 Repos): 14/22 CRITICAL, neue FP-Klassen der 10 neuen Repos noch offen → Phase 2 (Tuning + Perf-Index). Nachweis Vorher/Nachher-Tabelle in benchmark-results.md.
- [x] A4 **Mod-Detektoren:** 3 neue (Prompt-Compose-Rewrite, Tool-Call-Argument-Rewrite, Update-Delta-Trojan) in `modvet/detectors_extra.py` + 6 Fixture-Tests grün (18.10., Subagent-Bau + Dispatcher-Integration); Hook-Permission-Lift war vorhanden.
- [x] A5 **OWASP-Mapping:** jedes Finding trägt `owasp_mcp` (Kategorie→MCP01–MCP10-Mapping in engine.py), ausgegeben in JSON + Human-Report (19.10.)
- [x] A6 **SARIF-Output:** `modvet scan --format sarif` (SARIF 2.1.0, GitHub-Code-Scanning-kompatibel) + 4 Schema-Tests grün (18.10.)
- [x] A7 **Badge:** `modvet badge --input report.json --out badge.svg` (CLEAN/WARN/CRITICAL-Farben) + 5 Tests grün (18.10.)
- [x] A8 **Verteilung fertig:** `uv build` erzeugt wheel + sdist (modvet-0.1.0, 19.10. verifiziert); README mit Vergleichstabelle (vs. Snyk/mcp-triage). npm-Publish bleibt Jörg-GO.
- [~] A9 **Verification:** Test-Suite grün (5 + 6 + 4 + 5 = 20 Tests, 19.10.); Benchmark-Bericht im Repo aktualisiert; Spec-Checkboxen: A1–A8 abgehakt, A3/A9-Voll-Corpus-Nachweis = Phase-2-Arbeit (neue FP-Klassen: Code-Obfuscation in Hook-Sammlungen, Data-Exfil in DevOps-Skills, Laufzeit-Ø 41 s → Perf-Index).

## Non-Goals (v0.2)
Kein Web-UI · keine Cloud-API · keine Badge-REGISTRY (nur Badge-Generator) · kein LLM-Judge (bleibt deterministisch) · keine Publikation · keine neuen Abhängigkeiten über stdlib hinaus.

## Phasen
0. Audit + Benchmark (A1+A2) → 1. Detektoren + FP-Fixes (A3+A4) → 2. Mapping + Outputs (A5–A7) → 3. Packaging + Docs (A8) → 4. Converge (A9).

## Verification
`python tests/run_tests.py` (alle Tests grün) + `python tools/benchmark.py` (Tabelle) + `uv build` (Artefakte existieren) + Spec-Checkboxen.
