"""ModVet v0.2 — Zusätzliche Mod-Sicherheits-Detektoren (stdlib only).

Drei Detektoren scannen eine Mod-Textdatei (relativer Pfad + Inhalt) und
geben eine Liste von Finding-Objekten zurück (Kategorie „Mod Capability“):

    scan_file(rel_path: str, text: str) -> list

Detektor 1  „Prompt Compose Rewrite“   — Prompt-APIs werden überschrieben
            (prompt.compose, promptModifier, modifyPrompt, preprocessPrompt,
            setSystemPrompt mit Zuweisung/Definition). Severity HIGH.
Detektor 2  „Tool Call Argument Rewrite“ — PreToolUse-Hook-Logik mutiert
            Tool-Eingaben (Zuweisung an input./tool_input./toolUseInput. im
            3-Zeilen-Fenster). Severity HIGH.
Detektor 3  „Update Delta Trojan“      — Update-/Install-Skript (.sh/.js/.py
            mit update/postinstall/upgrade im Dateinamen) lädt Code herunter,
            macht ihn ausführbar und startet ihn (5-Zeilen-Fenster).
            Severity CRITICAL.

Keine externen Dependencies. Die Integration in die bestehende Engine
(Scan-Orchestrierung, Reporting) übernimmt der Auftraggeber.
"""

import re
from pathlib import Path

from modvet.core.engine import Finding, Severity

CATEGORY = "Mod Capability"

# ─── Detektor 1: Prompt Compose Rewrite ─────────────────────────────────────
# Prompt-API-Namen, die per Zuweisung, Neudefinition oder Property-Override
# überschrieben werden. Reine Aufrufe (prompt.compose(...), modifyPrompt(...))
# schlagen NICHT an — erst die Manipulation der API selbst.

_RE_PROMPT_COMPOSE = re.compile(
    r"(?i)(?:"
    r"^\s*(?:async\s+)?(?:def|function)\s+(?:promptModifier|modifyPrompt|preprocessPrompt|setSystemPrompt)\s*\(|"
    r"(?:promptModifier|modifyPrompt|preprocessPrompt|setSystemPrompt)\s*[:=]|"
    r"prompt\s*\.\s*compose\s*[:=]|"
    r"\.\s*setSystemPrompt\s*[:=]"
    r")"
)

# ─── Detektor 2: Tool Call Argument Rewrite ─────────────────────────────────
# PreToolUse-Hook-Logik, die Tool-Eingaben mutiert: Hook-Zeile + Zuweisung an
# input.* / tool_input.* / toolUseInput.* im selben 3-Zeilen-Fenster.

_RE_PRETOOLUSE = re.compile(r"(?i)PreToolUse")
_RE_TOOL_INPUT_ASSIGN = re.compile(
    r"(?i)\b(?:toolUseInput|tool_input|input)\s*\.\s*\w+\s*=(?!=|>)"
)

# ─── Detektor 3: Update Delta Trojan ────────────────────────────────────────
# In Update-/Install-Skripten: Download (curl/wget) + chmod mit Ausführ-Bit +
# Ausführung der Datei — alle drei Schritte innerhalb von 5 Zeilen.

_RE_UPDATE_NAME = re.compile(r"(?i)(?:update|postinstall|upgrade)")
_RE_DOWNLOAD = re.compile(r"(?i)\b(?:curl|wget)\b")
_RE_CHMOD_X = re.compile(
    r"(?i)\bchmod\b\s+(?:"
    r"[0-7]{3,4}\b|"
    r"\+[a-zA-Z]*x[a-zA-Z]*|"
    r"[augo]+\+[a-zA-Z]*x[a-zA-Z]*|"
    r"[augo]+=[a-zA-Z]*x[a-zA-Z]*"
    r")"
)
_RE_EXEC = re.compile(
    r"(?i)(?:^|[;&|]\s*)(?:"
    r"\./[\w./-]+|"
    r"\b(?:sh|bash|zsh|node|npm|python3?|exec|source)\s+[^\s;|&]+|"
    r"[^\s;|&<>]+\.(?:sh|py|js)\b"
    r")(?=\s|$)"
)

__all__ = [
    "scan_file",
    "detect_prompt_compose_rewrite",
    "detect_tool_call_argument_rewrite",
    "detect_update_delta_trojan",
]


def detect_prompt_compose_rewrite(rel_path: str, text: str) -> list:
    """Erkennt Code, der Prompt-APIs überschreibt oder neu definiert.

    Schlägt an bei: prompt.compose = ..., promptModifier/modifyPrompt/
    preprocessPrompt/setSystemPrompt mit Zuweisung, Property-Override
    (obj.setSystemPrompt = ...) oder Funktions-Neudefinition.
    """
    findings = []
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        match = _RE_PROMPT_COMPOSE.search(line)
        if not match:
            continue
        context = "\n".join(lines[max(0, idx - 1): idx + 2])
        findings.append(
            Finding(
                severity=Severity.HIGH,
                category=CATEGORY,
                pattern_name="Prompt Compose Rewrite",
                matched_text=match.group(0),
                line_number=idx + 1,
                context=context,
                recommendation=(
                    "Prompt-Compose-API wird überschrieben oder neu definiert. "
                    "Ein Mod kann damit sämtliche Prompts des Agenten umleiten "
                    "oder manipulieren. Mod nicht ohne manuelle Code-Prüfung "
                    "installieren und den Hook isoliert testen."
                ),
                confidence=90,
            )
        )
    return findings


def detect_tool_call_argument_rewrite(rel_path: str, text: str) -> list:
    """Erkennt PreToolUse-Hooks, die Tool-Eingaben mutieren.

    Bedingung: Eine Zeile enthält „PreToolUse“ UND im selben 3-Zeilen-Fenster
    (Hook-Zeile + zwei Folgezeilen) steht eine Zuweisung an
    input./tool_input./toolUseInput.
    """
    findings = []
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if not _RE_PRETOOLUSE.search(line):
            continue
        window = lines[idx: idx + 3]
        for offset, window_line in enumerate(window):
            if _RE_TOOL_INPUT_ASSIGN.search(window_line):
                findings.append(
                    Finding(
                        severity=Severity.HIGH,
                        category=CATEGORY,
                        pattern_name="Tool Call Argument Rewrite",
                        matched_text=window_line.strip(),
                        line_number=idx + offset + 1,
                        context="\n".join(window),
                        recommendation=(
                            "PreToolUse-Hook mutiert Tool-Eingaben (Zuweisung an "
                            "input./tool_input./toolUseInput.). Der Mod kann "
                            "Tool-Aufrufe des Agenten umleiten, Befehle ändern "
                            "oder Daten abfangen. Hook-Logik manuell prüfen."
                        ),
                        confidence=90,
                    )
                )
                break
    return findings


def detect_update_delta_trojan(rel_path: str, text: str) -> list:
    """Erkennt Trojan-Muster in Update-/Install-Skripten.

    Bedingungen: (1) Datei ist .sh/.js/.py und der Dateiname enthält
    update/postinstall/upgrade; (2) im Inhalt folgen auf eine
    curl/wget-Zeile innerhalb von 5 Zeilen ein chmod mit Ausführ-Bit und die
    Ausführung einer Skriptdatei.
    """
    findings = []
    path = Path(rel_path)
    if not _RE_UPDATE_NAME.search(path.stem):
        return findings
    if path.suffix.lower() not in (".sh", ".js", ".py"):
        return findings

    lines = text.splitlines()
    for download_idx, line in enumerate(lines):
        if not _RE_DOWNLOAD.search(line):
            continue
        window = lines[download_idx: download_idx + 5]

        chmod_idx = None
        exec_idx = None
        for offset, window_line in enumerate(window):
            if chmod_idx is None and _RE_CHMOD_X.search(window_line):
                chmod_idx = offset
            if _RE_EXEC.search(window_line):
                exec_idx = offset
                break

        if chmod_idx is None or exec_idx is None or exec_idx < chmod_idx:
            continue

        key_lines = [
            window[0].strip(),
            window[chmod_idx].strip(),
            window[exec_idx].strip(),
        ]
        matched_text = " | ".join(dict.fromkeys(key_lines))
        findings.append(
            Finding(
                severity=Severity.CRITICAL,
                category=CATEGORY,
                pattern_name="Update Delta Trojan",
                matched_text=matched_text,
                line_number=download_idx + 1,
                context="\n".join(window),
                recommendation=(
                    "Update-/Install-Skript lädt Code aus dem Netz, macht ihn "
                    "ausführbar und startet ihn — klassisches Trojan-Muster "
                    "(Update-Delta). Download-Quelle verifizieren; Skript "
                    "niemals ungeprüft ausführen."
                ),
                confidence=95,
            )
        )
    return findings


def scan_file(rel_path: str, text: str) -> list:
    """Scannt eine Mod-Textdatei mit allen drei Detektoren.

    Args:
        rel_path: Pfad der Datei relativ zum Mod-Root (z. B. „hooks/update.sh“).
        text:    Inhalt der Datei als String.

    Returns:
        Liste von Finding-Objekten (Kategorie „Mod Capability“).
    """
    findings = []
    findings.extend(detect_prompt_compose_rewrite(rel_path, text))
    findings.extend(detect_tool_call_argument_rewrite(rel_path, text))
    findings.extend(detect_update_delta_trojan(rel_path, text))
    return findings
