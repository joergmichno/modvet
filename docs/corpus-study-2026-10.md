# Corpus-Studie: 21 populäre Claude-Code-Mods mit ModVet 0.2.4 gescannt

**Datum:** 24.10.2026 · **Engine:** ModVet 0.2.4 (frische PyPI-Installation, 236 deterministische Pattern, 0 Dependencies)
**Methode:** Voll-Scan aller 22 Benchmark-Repos (`benchmark/rescan-2026-10-24/`, JSON-Rohdaten je Repo) + **manuelle Verifikation aller CRITICAL-Cluster** der Top-Repos. `davila7__claude-code-templates` ist **nicht vollständig** in dieser Statistik: Der Vollscan (8.050 Dateien, 140 MB) wurde nach langer Laufzeit abgebrochen — die langsamsten Dateien sind Benchmark-/Minified-JSONs (bis ~90 s/Datei). Der Perf-Fix in v0.2.5 (52,2 s → 0,45 s für die 765-KB-Testzeile) behebt die Hauptursache, aber nicht alle Großdateien; weitere Optimierung ist offen. Er wird als **Laufzeit-Befund** dokumentiert statt als fertiges Repo.
**Wichtig:** `benchmark/results.json` ist Stand VOR der FP-Verfeinerung (1.817 Findings) und wird hier NICHT zitiert.

## Zahlen (21 Repos)

- **1.466 Findings gesamt** — davon 170 CRITICAL · 499 HIGH · 460 MEDIUM · 337 LOW
- **Top-Kategorien:** Prompt Injection 442 · Code Obfuscation 238 · Shell Injection 229 · Dangerous Command 190 · Data Exfiltration 115 · Social Engineering 87 · Agentic Security 72 · Mod Capability 53
- **1 Repo komplett clean:** scasella__claude-flightdeck (0 Findings) · oikon48__prompt-rail nur 1 LOW · BeLazy167 nur 1 MEDIUM

| Repo | Findings | CRIT | HIGH | MED | LOW |
|---|---|---|---|---|---|
| EveryInc__compound-engineering-plugin | 509 | 47 | 181 | 198 | 83 |
| akin-ozer__cc-devops-skills | 231 | 43 | 61 | 22 | 105 |
| wshobson__agents | 169 | 41 | 51 | 67 | 10 |
| costajohnt__oss-autopilot | 150 | 21 | 54 | 54 | 21 |
| karanb192__claude-code-hooks | 74 | 11 | 30 | 31 | 2 |
| disler__claude-code-hooks-multi-agent-observability | 57 | 0 | 8 | 16 | 33 |
| disler__claude-code-hooks-mastery | 49 | 0 | 5 | 11 | 33 |
| zenbu-labs__terminal-browser | 47 | 3 | 26 | 9 | 9 |
| hesreallyhim__awesome-claude-code | 36 | 0 | 20 | 6 | 10 |
| claude-code-mods-main | 35 | 1 | 33 | 1 | 0 |
| anthropics__claude-code-security-review | 32 | 0 | 5 | 9 | 18 |
| es617__claude-replay | 30 | 1 | 4 | 20 | 5 |
| NahumLitvin__prismantis | 16 | 0 | 6 | 6 | 4 |
| briansmith80__claude-code-status-bar | 11 | 2 | 4 | 4 | 1 |
| data-goblin__claude-code-filetree | 6 | 0 | 1 | 4 | 1 |
| jarrodwatts__claude-image-view | 6 | 0 | 6 | 0 | 0 |
| karanb192__cache-tax | 4 | 0 | 2 | 1 | 1 |
| noeltock__mod-builder | 2 | 0 | 2 | 0 | 0 |
| BeLazy167__claude-mods-skill | 1 | 0 | 0 | 1 | 0 |
| oikon48__prompt-rail | 1 | 0 | 0 | 0 | 1 |
| scasella__claude-flightdeck | 0 | 0 | 0 | 0 | 0 |

## Manuelle Verifikation: Was die CRITICALs wirklich sind

**Kernaussage: Die große Mehrheit der CRITICAL-Findings ist KEIN Angriff, sondern erwartbarer Kontext.** Konkret verifiziert (Code gelesen, nicht nur JSON):

| FP-Klasse | Beispiele (verifiziert) |
|---|---|
| Test-Fixtures / Negativ-Tests | EveryInc: `rm -rf /` in Test-String, `Read ~/.ssh/id_rsa` als Injection-Test · claude-code-mods-main: `cat config/.env.production` in Test |
| Security-Tool-Eigen-Code | karanb192: `block-dangerous-commands.js` (mkfs/curl-Muster = Detektionslisten) · claude-code-mods-main: `secret-box/detect.ts` (Regex-Sammlung) |
| Doku-/Plan-Prosa | EveryInc: 20× „Toxic Flow" aus Wortkombinationen wie „read … post" in docs/plans |
| Echo-/Hinweis-Zeilen | briansmith80: `echo "curl … | bash"` (Installationsanleitung) · akin-ozer: helm-setup echo |
| Zahlen als „Kreditkarte" | wshobson: 21× Dezimalzahlen in `evals/static-score-snapshot.json` (bekannte FP-Klasse) |
| Plattform-Normalität | wshobson: 169.254.169.254 in Network-Policy-Template · akin-ozer: K8s-readinessProbe als „Exfiltration Chain" |

**Verbleibender echter Hardening-Hinweis (1):**
- **zenbu-labs/terminal-browser** — `cli/src/upgrade.ts:29`: Self-Update führt `curl -fsSL '<url>' | bash` aus; URL kommt aus einem Remote-Manifest (`shared/src/release.ts:37-44`), dessen Origin per `TERMINAL_BROWSER_RELEASE_ORIGIN` überschreibbar ist. Keine Integritätsprüfung (SHA-256/Signatur). Legitimer Supply-Chain-Hardening-Vorschlag → Issue-Entwurf in `work/distribution/issue-entwuerfe.md` (Jörg-GO).

## Was das für ModVet bedeutet (ehrlich)

1. **Die FP-Verfeinerung wirkt** (1.817 → 1.466 Findings bei 21 statt 22 Repos), aber die verbleibenden CRITICALs sind überwiegend Kontext-Klassen. **Nächster Engine-Hebel: Kontext-Refiner für Test-/Doku-/Security-Tool-Code** — nicht mehr Pattern.
2. **Für Nutzer zählt der verifizierte Befund, nicht die Rohzahl.** Deshalb ist der Evidence-Report (Datei+Zeile+Regel+Ruleset-Hash) das zentrale Produkt-Feature: Er macht genau diese manuelle Prüfung reproduzierbar.
3. **Kein Massen-Outreach.** Ein verifizierter Hinweis (zenbu-labs) ist mehr wert als 10 FUD-DMs. Die Studie selbst ist das Distributions-Artefakt.

## Reproduktion
```bash
pip install modvet==0.2.4
modvet scan <repo> --json --evidence evidence.json
```
Rohdaten: `benchmark/rescan-2026-10-24/*.json` · Aggregator: `benchmark/corpus-study-generator.py` · Scan-Treiber: `benchmark/rescan-distribution.py`
