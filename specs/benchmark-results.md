# Benchmark-Baseline (16.10., Phase 0) — 12 echte Mod-Repos

> `tools/benchmark.py` + Corpus `benchmark/corpus/` (awesome-claude-code-mods-Katalog). Stand VOR der Optimierung.

## Phase-1-Ergebnis (18.10., Commit 1c6f720)

| Metrik | Phase 0 | Phase 1 | Delta |
|---|---|---|---|
| Findings gesamt | 1.815 | **461** | **−75 %** |
| Ø Findings/Repo | 151 | **38,4** | −75 % |
| Ø Laufzeit/Repo | 15,5 s | ~15,0 s | ~gleich (Perf-Phase offen) |
| CRITICAL-Repos | 12/12 | 8/12 | 4 Repos nun HIGH |

Umgesetzt: Capability-Kombinationslogik + Nähe-Kriterium (≤3 Zeilen), Risk-Level aus
höchster Severity, Refiner-Kaskade (Doku/Code, README≠Instruktion, JS-Template-Literals,
Standard-Bash, Fixtures, Zitat-Filter), Severity-Rekalibrierung. 5/5 Tests grün.

**Offen (Phase 1b):** verbleibende CRITICAL-Treiber je Repo prüfen — karanb-hooks
(Shell-Pipe×29: echte Install-Skripte vs. Doku?), claude-code-mods-main (Prompt-Injection×24
im Security-Test-Repo), zenbu terminal-browser (Curl-Pipe×9). Danach Phase 2/3 (Detektor-Redesign,
OWASP-Mapping, SARIF, Badge, Build).

## Ergebnis

| Metrik | Wert |
|---|---|
| Repos | 12 |
| Findings gesamt | **1.815** |
| Ø Findings/Repo | **151** |
| Ø Laufzeit/Repo | **15,5 s** (Spitze: 44,6 s) |
| Risiko-Label | **CRITICAL bei allen 12** |

## Kategorien (top)

Mod Capability 777 · Shell Injection 290 · Output Injection 226 · Data Exfiltration 171 · Code Obfuscation 125 · Prompt Injection 88 · Dangerous Command 86 · Rest ~50.

## Diagnose (3 Hauptursachen)

1. **Capability-Scan ohne Kontext (777 Findings):** Jede Zeile mit `fetch`/`fs.write`/`exec`-Muster feuert — aber genau das IST die normale Arbeit eines Mods. Abhilfe: Kombinations-Logik (z. B. „Env-Read + POST" = Exfil-Verdacht; einzelner `fetch` = INFO, kein Finding) + Whitelist für harmlose Idiome.
2. **Text-Engine auf Code losgelassen (290+226):** Shell-/Output-Injection-Muster zielen auf LLM-Text (Backticks, `$()`), feuern aber in .ts-Dokumentation und Code-Beispielen. FP-Refiner (Kommando-Verb) reicht nicht. Abhilfe: Muster-Kontext trennen (docs vs. code), Refiner verschärfen, Kategorie-Kappung je Dateityp.
3. **Kein einziges der 12 Repos ist nachweislich bösartig → die FP-Quote ist faktisch ~100 %.** Ein Scanner, der bei jedem sauberen Mod 151 CRITICAL-Alarme schreit, wird nicht installiert. Ziel A3: <20 % FP-Quote.

## Perfomance-Ursache

Engine wird pro Datei aufgerufen (O(Dateien × Zeilen × Pattern)); große Repos (44,6 s) sprengen jedes Pre-Install-Gefühl. Abhilfe: Pattern-Precompiling, Datei-Batching, Größen-/Dateizahl-Cap mit klarer Meldung.

## Nächste Schritte (Phase 1)

Detektor-Redesign (Kontext-Aware Capabilities), FP-Refiner v2, Batch-Scan, Severity-Neukalibrierung (236 Pattern: nur 3 LOW = Schieflage). Danach Re-Benchmark gegen dieselbe Baseline-Tabelle.
