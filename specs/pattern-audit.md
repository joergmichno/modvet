# Pattern-Audit (A1) — Stand 18.10.2026 (Phase 1a–1d)

> Kategorisierung der ModVet-Pattern-Basis, Veraltungs-Markierung, Lücken-Analyse gegen
> OWASP MCP Top 10 + Mod-spezifische Vektoren. Grundlage: Engine-Port aus ClawGuard
> (~236 Pattern, Juli 2026) + ModVet-eigene Detektoren.

## 1. Kategorien + OWASP-MCP-Mapping (A5)

| Kategorie | Musterzahl (ca.) | OWASP MCP | Anmerkung |
|---|---|---|---|
| Prompt Injection | ~100 | MCP01 | Kern-Vektor für Mods (SKILL.md/Instruktionen) |
| Social Engineering | ~15 | MCP01 | Verhaltens-Manipulation |
| Dangerous Command | ~30 | MCP05 | rm -rf, curl\|sh, RCE |
| Shell Injection | ~20 | MCP05 | $(), Backticks, child_process |
| Output Injection | ~10 | MCP05 | LLM-Output in Kommando-Kontext |
| Code Obfuscation | ~25 | MCP05 | eval/exec/getattr, Base64-Follow |
| Data Exfiltration (+PII) | ~25 | MCP02 | Secrets, PII, Sensitive-File-Requests |
| Agentic Security | ~10 | MCP03 | Approval-Bypass, Excessive Agency |
| Tool Manipulation | ~8 | MCP04 | Tool-Definition-Tampering, MCP Rug Pull |
| Supply Chain | ~5 | MCP07 | Dependency-Install-Risiken |
| Mod Capability (ModVet-eigen) | 7 Primitive + 5 Kombinationen | MCP03 | Hook-Lift, Config-Rewrite, Exfil-Kombinationen |
| MCP Config (ModVet-eigen) | 1 | MCP08 | mcpServers-Manifest |

## 2. Veraltungs-Befunde (aus Phase 0/1)

- **Summen-Overflow-Risk:** Risk-Score war Summe aller Severities → jeder Mod CRITICAL. GEFIXT: höchste Einzel-Severity (18.10.).
- **Kontextlose Einzel-Capabilities:** fetch/process.env/fs.write feuerten einzeln (777 FPs). GEFIXT: Kombinationslogik + Nähe-Kriterium (18.10.).
- **Text-Muster auf Code:** Shell-/Output-Injection feuerten auf Doku/Code-Beispielen. GEFIXT: Doku-vs-Instruktion-Semantik + Dateityp-Kappung.
- **Severity-Schieflage:** Substitution/subprocess/eval waren CRITICAL obwohl Standard-Bash/Python. GEFIXT: Rekalibrierung → MEDIUM.
- **Security-Mod-Verwechslung:** Testfälle/Beschreibungen eigener Abwehr wurden als Angriff gemeldet. GEFIXT: Test-Kontext-Filter.

## 3. Lücken gegen OWASP MCP Top 10

| OWASP MCP | Abdeckung | Lücke |
|---|---|---|
| MCP01 Prompt Injection | gut (100+ Muster, Evasion-Varianten) | Mehrsprachige Override-Muster (FR/ES) fehlen — nachrüstbar |
| MCP02 Sensitive Disclosure | gut (Secrets, PII, File-Access) | Kein Entropie-Secret-Scan (nur Format-Pattern) |
| MCP03 Excessive Agency | mittel (Hook-Lift, Approval-Bypass) | Kein Capability-Permissions-Vergleich (declared vs. used) |
| MCP04 Tool Poisoning | mittel (MCP Rug Pull, Tampering) | Tool-Description-Injection nicht explizit |
| MCP05 Cmd/Script Injection | gut (5 Kategorien) | — |
| MCP06 Unbounded Consumption | FEHLT | kein Detektor für Endlos-Loops/Ressourcen-Muster |
| MCP07 Supply Chain | schwach (5 Muster) | package.json-Skripte (pre/postinstall) nicht geprüft → A4-Detektor |
| MCP08 Insecure Deployment | schwach (MCP Config) | .env-Commit-Erkennung, Permissions-Overrides |
| MCP09 CSRF | FEHLT | Server-Empfehlung: kein Auto-Forward von MCP-Calls |
| MCP10 Authorization | FEHLT | für Mod-Scans begrenzt relevant (Client-seitig) |

## 4. Mod-Vektor-Lücken (→ A4-Detektoren, 18.10. beauftragt)

| Vektor | Status |
|---|---|
| hooks/register.ts Permission-Lift | ✓ vorhanden (Primitive „Hook Permission Lift") |
| prompt.compose / promptModifier Rewrite | NEU: detectors_extra.py (Prompt Compose Rewrite) |
| PreToolUse Tool-Call-Argument-Rewrite | NEU: detectors_extra.py (Tool Call Argument Rewrite) |
| Update-Delta-Trojan (postinstall/update.sh) | NEU: detectors_extra.py (Update Delta Trojan) + diff-Snapshot in CLI |
| MCP-Manifest-Import (mcpServers) | ✓ vorhanden (MCP Manifest) |

## 5. Nächste Schritte

- A4-Detektoren in scan_single_file integrieren (sobald detectors_extra.py verifiziert).
- MCP06/MCP09/MCP10: als bewusste Nicht-Ziele dokumentieren (Client-Scanner-Grenze) — keine Phantom-Abdeckung.
- package.json-Script-Scan (MCP07) als Primitive ergänzen.
