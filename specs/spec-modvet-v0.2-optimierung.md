# Spec: ModVet v0.2 — Full-Optimization (Engine + Patterns + Verteilung)

> 16.10.2026 · Jörg-Entscheid („Full-Optimierungs-Prozess, da bereits veraltet") · Kosten: 0 €
> Ausgangslage: Gerüst v0.1 (15.10.) frisch, aber Engine-Port = ClawGuard-Kern von ~Juli 2026 (236 Pattern, vor der Mod-Ära entstanden). Veraltung liegt in der ERKENNUNG, nicht im Gerüst.

## Goal
ModVet von einem Port alter ClawGuard-Muster zu einem **mod-zeitgemäßen Scanner** machen: Pattern-Basis am Stand Okt 2026, gemessene FP/TP-Raten statt Bauchgefühl, OWASP-MCP-Mapping, saubere Verteilung.

## Acceptance-Kriterien (fertig heißt:)

- [ ] A1 **Pattern-Audit:** alle 236 CSV-Pattern kategorisiert (Prompt-Injection/Command/Social/…), veraltete/irrelevante markiert, Lücken gegen OWASP MCP Top 10 (MCP01–MCP10) + Mod-Vektoren (hooks/register.ts, prompt.compose, tool-call-rewriting, update-drift) dokumentiert → `specs/pattern-audit.md`
- [ ] A2 **Benchmark-Corpus:** ≥20 echte Mods (aus awesome-claude-code-mods-Katalog + mods.aidojo.si) lokal gespiegelt; Mess-Skript `tools/benchmark.py` liefert je Mod: Findings, Laufzeit, FP-Quote (manuelle Klassifikation in `specs/benchmark-results.md`)
- [ ] A3 **FP-Quote gesenkt:** FP-Quote (Findings ohne echten Angriff auf Clean-Mods) < 20 % auf dem Corpus — Refiner + Pattern-Fixes nachgewiesen per Vorher/Nachher-Tabelle
- [ ] A4 **Mod-Detektoren:** ≥3 neue mod-spezifische Detektoren (Hook-Permission-Lift erweitert, prompt.compose-Rewrite, Tool-Call-Argument-Rewrite, Update-Delta-Trojan-Muster) mit je ≥1 Fixture-Test
- [ ] A5 **OWASP-Mapping:** jedes Detektor-Cluster auf OWASP MCP Top 10 gemappt (im JSON-Report als Feld `owasp_mcp`)
- [ ] A6 **SARIF-Output:** `modvet scan --format sarif` (GitHub-Code-Scanning-kompatibel), Test: SARIF-Schema-Pflichtfelder vorhanden
- [ ] A7 **Badge:** `modvet badge --input report.json --out badge.svg` (CLEAN/WARN/CRITICAL) + Test
- [ ] A8 **Verteilung fertig:** `uv build` läuft, wheel + sdist erzeugbar; README mit Vergleichstabelle (vs. Snyk/mcp-triage) — npm-Publish bleibt Jörg-GO
- [ ] A9 **Verification:** Test-Suite (alle bisherigen + neuen) grün; Benchmark-Bericht im Repo; Spec-Checkboxen alle abgehakt

## Non-Goals (v0.2)
Kein Web-UI · keine Cloud-API · keine Badge-REGISTRY (nur Badge-Generator) · kein LLM-Judge (bleibt deterministisch) · keine Publikation · keine neuen Abhängigkeiten über stdlib hinaus.

## Phasen
0. Audit + Benchmark (A1+A2) → 1. Detektoren + FP-Fixes (A3+A4) → 2. Mapping + Outputs (A5–A7) → 3. Packaging + Docs (A8) → 4. Converge (A9).

## Verification
`python tests/run_tests.py` (alle Tests grün) + `python tools/benchmark.py` (Tabelle) + `uv build` (Artefakte existieren) + Spec-Checkboxen.
