"""ModVet — Mod-Discovery + Capability-Scanning für Claude-Code-Mods.

Zwei Schichten:
1. Engine-Scan (modvet.core.engine): Prompt-Injection / Dangerous-Commands / Social-Engineering
   auf allen Textdateien eines Mods.
2. Capability-Scan (v0.2-Phase-1, kontextbewusst): Einzel-Capabilities (fetch, process.env,
   fs.write, exec) sind NORMALE Mod-Arbeit und feuern NICHT mehr als Einzel-Findings.
   Findings entstehen erst durch KOMBINATIONEN (Env-Read + POST = Exfil-Pfad,
   Exec + Fetch = Download-and-Run) oder durch echte Angriffsprimitive
   (Hook-Permission-Lift, Reverse Shell, Hardcoded Secret, Config-Rewrite).
Deterministisch, offline, kein LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
import re

from .core.engine import CATEGORY_OWASP_MCP, Finding, ScanReport, Severity, scan_text

MOD_EXTENSIONS = {
    ".ts", ".js", ".mjs", ".cjs", ".json", ".md", ".txt",
    ".py", ".sh", ".yaml", ".yml", ".toml",
}
SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", ".modvet"}
MAX_FILE_BYTES = 1_000_000

# ─── Angriffsprimitive: feuern einzeln, kontextfrei (bleiben CRITICAL/HIGH) ──
ATTACK_PRIMITIVES: list[tuple[str, str, Severity, str]] = [
    (
        "Shell Pipe Download",
        r"(curl|wget)[^\n|]{0,200}\|\s*(ba)?sh\b",
        Severity.CRITICAL,
        "Piped download executed in shell — classic trojan install pattern.",
    ),
    (
        "Base64 Decode Execute",
        r"(echo|printf|cat|printf)[^\n|]{0,200}\|\s*base64\s+(-d|--decode)?[^\n|]{0,200}\|\s*(ba)?sh\b",
        Severity.CRITICAL,
        "Base64-decoded payload piped into shell — obfuscated code execution.",
    ),
    (
        "Reverse Shell",
        r"(nc\s+-[a-z]*e\b|/dev/tcp/|python3?\s+-c\s*['\"].{0,60}(socket|subprocess))",
        Severity.CRITICAL,
        "Reverse-shell or raw process-spawn primitives.",
    ),
    (
        "Hook Permission Lift",
        r"(canUseTool|isEnabledForTool|allowTool)[^\n]{0,120}(return\s+(true|!))",
        Severity.CRITICAL,
        "Hook lifts tool permissions (deny-rule bypass pattern).",
    ),
    (
        "Config Rewrite",
        r"(claude\.json|settings\.json|\.claude)[^\n]{0,80}(writeFile|appendFile|write\(|override|replace)",
        Severity.HIGH,
        "Modifies Claude configuration files at runtime.",
    ),
    (
        "Hardcoded Secret",
        r"(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})",
        Severity.CRITICAL,
        "Hardcoded API key / token pattern — must never ship in a mod.",
    ),
    (
        "Secret Assignment",
        r"(api[_-]?key|secret|token|password|passwd)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
        Severity.CRITICAL,
        "Plaintext credential assignment — move to env config.",
    ),
]

# ─── Capability-Inventar: je Datei gesammelt, feuern nur in Kombination ──────
CAPABILITY_MARKERS: dict[str, re.Pattern] = {
    "exec": re.compile(r"(child_process|execSync|spawnSync|\bspawn\s*\(|\bexec\s*\(|\bshelljs\b|os\.system\b|Runtime\s*\.\s*getRuntime)"),
    "env_read": re.compile(r"(process\.env|import\.meta\.env|\.env\.get\b|\bgetenv\s*\()"),
    "file_write": re.compile(r"(fs\.writeFile|fs\.appendFile|writeFileSync|appendFileSync|fs\.write\s*\(|write_text\s*\(|open\s*\([^)]*['\"]w)"),
    "http_post": re.compile(r"method\s*:\s*['\"]POST['\"]|\.post\s*\(|requests\.post\s*\(|curl\s+[^\n]*(-X\s*POST|--data|--json)"),
    "net_fetch": re.compile(r"\bfetch\s*\(|XMLHttpRequest|http\.request|requests\.(get|put)|\.get\s*\("),
}

# Kombinationsregeln: (Menge nötiger Marker, Name, Severity, Empfehlung)
COMBINATION_RULES: list[tuple[frozenset[str], str, Severity, str]] = [
    (
        frozenset({"env_read", "http_post"}),
        "Env-Read + POST (Exfil-Pfad)",
        Severity.HIGH,
        "Liest Umgebungsvariablen UND sendet HTTP-POST — klassischer Exfiltrationspfad. Prüfe, ob Secrets im POST-Body landen.",
    ),
    (
        frozenset({"env_read", "net_fetch"}),
        "Env-Read + Fetch (Exfil-Pfad)",
        Severity.HIGH,
        "Liest Umgebungsvariablen UND ruft externe URLs — prüfe, ob Secret-Werte in die URL/Body fließen.",
    ),
    (
        frozenset({"exec", "http_post"}),
        "Exec + POST (Command-Output-Exfil)",
        Severity.HIGH,
        "Führt Prozesse aus UND sendet HTTP-POST — prüfe, ob Kommando-Ausgaben übertragen werden.",
    ),
    (
        frozenset({"exec", "net_fetch"}),
        "Exec + Fetch (Download-and-Run-Pfad)",
        Severity.MEDIUM,
        "Führt Prozesse aus UND lädt Inhalte — potenzieller Download-and-Execute-Pfad, aber auch übliche Mod-Arbeit (Updates).",
    ),
    (
        frozenset({"file_write", "env_read"}),
        "File-Write + Env-Read",
        Severity.MEDIUM,
        "Schreibt Dateien und liest Umgebungsvariablen — prüfe Schreibziele (Config-Dateien, Startup-Hooks).",
    ),
]


@dataclass
class _CapInv:
    markers: dict[str, tuple[int, int]] = field(default_factory=dict)  # marker → (erste, letzte Zeile)


# Kombinationen feuern nur, wenn die Marker räumlich beieinander liegen
# (derselbe Ausdruck: echte Exfil-Calls wie body: process.env.KEY im fetch-POST).
# env-Read in Zeile 2 + POST in Zeile 500 = normale Mod-Struktur, kein Finding.
_MAX_MARKER_DISTANCE = 3

# Command-Execution-Muster: mehrere Treffer auf DERSELBEN Zeile sind EIN Problem
# (zenbu: curl|bash-Update = CurlPipe+RCE+ShellPipe gleichzeitig) → nur schwerstes behalten
_CMD_EXEC_PATTERNS = frozenset({
    "Shell Pipe Download",
    "Curl Pipe to Shell (LLM03)",
    "Remote Code Execution",
    "Base64 Decode Execute",
    "Destructive Shell Command",
    "Base64 Decode-and-Follow Command",
})

# Harmlose System-Aufräum-Pfade (apt-cache, /tmp): kein CRITICAL
_HARMLESS_CLEANUP_RE = re.compile(r"(/var/lib/apt/lists|/var/cache|/tmp(?:/|\"|'|\)|$))")


def _dedupe_cmd_line(findings: list[Finding]) -> list[Finding]:
    """Je Zeile max. 1 Command-Execution-Finding (das schwerste)."""
    best: dict[tuple[int, str], Finding] = {}
    for f in findings:
        if f.pattern_name in _CMD_EXEC_PATTERNS:
            key = (f.line_number, "cmd")
            if key not in best or f.severity.score() > best[key].severity.score():
                best[key] = f
    out = []
    for f in findings:
        if f.pattern_name in _CMD_EXEC_PATTERNS and best[(f.line_number, "cmd")] is not f:
            continue
        out.append(f)
    return out


def discover_mod_files(root: Path) -> list[Path]:
    """Alle scanbaren Dateien unter root (ohne node_modules/.git/...)."""
    out: list[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in MOD_EXTENSIONS and p.stat().st_size <= MAX_FILE_BYTES:
            out.append(p)
    return out


# FP-Reduktion: "Command Injection in Output" feuert auch auf Backticks in
# Code-Doku (`` `ps -axo ...` ``). Nur behalten, wenn der Match tatsächlich
# nach Kommando aussieht (Kommando-Verb enthalten).
_COMMAND_VERBS = re.compile(
    r"(?i)\b(ps|ls|cat|rm|curl|wget|npm|npx|git|bash|sh|python3?|chmod|chown|sudo|nc|ssh|find|grep)\b"
)


_QUOTED_ENV_CMD = re.compile(r"[`\"'][^`\"']*\b(cat|source|read)\s+\.env\b[^`\"']*[`\"']")

_JS_EXTS = (".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx")

# Reine Projekt-Doku (keine Instruktionsdateien): Beschreibungen von
# Security-Mustern ("this blocks `cat .env`", "encoded in base64") sind FP.
# Instruktionsdateien (SKILL.md, *.prompt, CLAUDE.md, AGENTS.md) bleiben AKTIV.
_README_RE = re.compile(r"(^|/)(readme[^/]*|LICENSE|CHANGELOG[^/]*)\.(md|txt)$", re.I)
_DOC_DIR_RE = re.compile(r"(^|/)([^/]*docs?[^/]*|examples?)/", re.I)

# Test-/Beispiel-Fixtures enthalten bewusst Klartext-Credentials.
_FIXTURE_RE = re.compile(r"(test|fixture|example|demo|sample)", re.I)

_PROMPT_INJECTION_PATTERNS = (
    "Encoded Bypass (Base64 hint)",
    "Forget/Reset Override",
    "Indirect Prompt Extraction",
    "Backwards/Encoded Output Request",
    "Multi-Part String Assembly",
    "Template Injection (LLM05)",
)

# Security-Mods enthalten Angriffs-Muster als STRINGS in Tests/Beschreibungen
# (shouldBlock('curl | bash'), "this blocks `cat .env`"). Diese sind KEINE Angriffe.
_ATTACK_TEST_PATTERNS = (
    "Shell Pipe Download",
    "Base64 Decode Execute",
    "Reverse Shell",
    "Curl Pipe to Shell (LLM03)",
    "Destructive Shell Command",
    "Remote Code Execution",
    "Privilege Escalation",
    "Python subprocess/os.system",
)

# v0.2-Phase-2: Extraktions-/Reset-Muster feuern in Doku (.md/.txt außerhalb
# Instruktionsdateien) fast immer als BESCHREIBUNG ("You can print additional
# context...", "MCP servers can expose prompts...") — echter Vektor nur dort,
# wo der Text als Anweisung in den Agent-Kontext lädt (SKILL.md/*.prompt/...).
_PROMPT_DOC_FP_PATTERNS = (
    "System Prompt Extraction",
    "Print/Spellcheck Prompt Extraction",
    "Indirect Prompt Extraction",
    "Indirect Instruction Reset",
    "Forget/Reset Override",
    "Verification Bypass (ASI09)",
)
_TEST_CONTEXT_RE = re.compile(
    r"\b(shouldBlock|shouldFlag|shouldPass|shouldDetect|shouldThrow|shouldAllow|makePayload|buildPayload|bashBlocked|analyzeCommand|bracketedPaste)\s*\(|"
    r"\b(it|describe|test|expect|assert)\s*[\(:]"
)
_BLOCK_DESC_RE = re.compile(r"\b(blocks?|detects?|catches?|prevents?|filters?|denies?|guards?|trips?wire|audits?)\b", re.I)
_QUOTE_CHARS_RE = re.compile(r"[`\"']")

# Instruktionsdateien: hier bleibt der volle Schutz aktiv (das ist der Mod-Vektor)
_INSTRUCTION_FILE_RE = re.compile(r"(^|/)(SKILL\.md|CLAUDE\.md|AGENTS\.md|.*\.prompt)$", re.I)


def _is_readme_doc(source: str) -> bool:
    return bool(_README_RE.search(source) or _DOC_DIR_RE.search(source))


def _refine_code_findings(findings: list[Finding], source: str = "") -> list[Finding]:
    """Dateityp-bewusste FP-Kappung (v0.2-Phase-1):
    - In Doku (.md/.txt) sind Shell-/Output-Injection-Treffer fast immer Code-BEISPIELE
      (README: `` `rm -rf` ``, SQL-/HTML-Beispiele) → Kategorie droppen.
      Prompt-Injection-Muster bleiben in Doku AKTIV (das ist der eigentliche Mod-Vektor!).
    - In JS/TS sind Backticks Template-Literals (kein Shell-Kommando) → Substitution droppen.
    - In .sh sind $()/Backticks Standard-Bash; echte Angriffe sind über
      Pipe-Download/Base64 (CRITICAL) abgedeckt → Substitution droppen.
    - PII-Kontaktmuster (E-Mail/Telefon) sind in Mod-Readmes normal → droppen.
    - Sensitive File Access nur als ANWEISUNG, nicht als Zitat-Beispiel
      (`` `cat .env` `` in Doku-Beschreibungen = FP).
    - Output-Injection ohne Kommando-Verb (Backtick-Doku) fällt überall raus.
    """
    is_doc = source.endswith((".md", ".txt"))
    is_instruction = bool(_INSTRUCTION_FILE_RE.search(source))
    is_js = source.endswith(_JS_EXTS)
    is_sh = source.endswith((".sh", ".bash"))
    # Doku (keine Instruktionsdateien): Beschreibungen von Security-Verhalten sind FP
    plain_doc = is_doc and not is_instruction
    out = []
    for f in findings:
        if plain_doc and f.pattern_name in _ATTACK_TEST_PATTERNS:
            continue  # Install-/Beispiel-Zeilen in Doku (curl|sh, rm -rf)
        if plain_doc and f.category in ("Dangerous Command", "Agentic Security"):
            continue  # Doku beschreibt Security-Verhalten, weist nichts an
        if plain_doc and f.category == "Prompt Injection":
            line = f.context or f.matched_text or ""
            if _QUOTE_CHARS_RE.search(line) or _BLOCK_DESC_RE.search(line):
                continue  # Doku BESCHREIBT Injection-Muster (Zitat/Beschreibung), injiziert nicht
        if plain_doc and f.pattern_name == "Sensitive File Access Request":
            continue  # Doku-Beschreibung, keine Anweisung
        if is_doc and f.category in ("Shell Injection", "Output Injection"):
            continue  # Code-Beispiele in Doku sind keine Findings
        if is_doc and f.pattern_name in (
            "Package / Dependency Install",      # jede README hat Install-Befehle
            "Remote Code Execution",             # Beispiel-curl|bash → Pipe-Download deckt echten Vektor
            "Python eval/exec",                  # Doku-Codebeispiele
            "Password in Cleartext",             # Beispiel-Configs in READMEs
            "Database Connection String",        # Beispiel-Connection-Strings
        ):
            continue
        if not is_doc and f.pattern_name in (
            "Command Injection in Output (LLM05)",       # Strings in Code sind kein LLM-Output-Vektor
            "IP Address in Sensitive Context (LLM06)",   # Server-Adressen sind normal
        ):
            continue
        if _is_readme_doc(source) and (
            f.category in ("Prompt Injection", "Dangerous Command", "Agentic Security")
            or f.pattern_name in ("Sensitive File Access Request", "Hardcoded Secret", "Secret Assignment")
            or f.pattern_name in _PROMPT_INJECTION_PATTERNS
        ):
            continue  # README/docs beschreiben Security-Muster; keine Instruktionen
        if f.pattern_name in ("Password in Cleartext", "Database Connection String") and _FIXTURE_RE.search(source):
            continue  # Test-Fixtures mit bewussten Beispiel-Credentials
        if f.pattern_name in ("Hardcoded Secret", "Secret Assignment") and _FIXTURE_RE.search(source):
            continue  # Fake-Test-Keys (sk-abc... in Testausgaben)
        if is_js and f.pattern_name.startswith("Python "):
            continue  # Python-Muster in JS-Code (RegExp.exec ist kein Python-eval)
        if f.pattern_name == "MCP Rug Pull Detection":
            line = f.context or f.matched_text or ""
            if not re.search(r"\b(mcp|server(?:Name|Config)?)\b", line, re.I):
                continue  # kein MCP-Kontext (z.B. PrismJS-Sprachdefinitionen mit SELECT/SCHEMA)
        if f.pattern_name == "Destructive Shell Command" and ("/tmp" in (f.matched_text or "") or "/tmp" in (f.context or "")):
            f = replace(f, severity=Severity.MEDIUM)  # /tmp-Aufräumen ist präzise und harmlos
        if f.pattern_name == "Destructive Shell Command" and _HARMLESS_CLEANUP_RE.search(f.context or f.matched_text or ""):
            f = replace(f, severity=Severity.MEDIUM)  # apt-cache/-lists-Cleanup ist Standard-Systempflege
        if f.pattern_name == "Python Dangerous File I/O":
            line = f.matched_text or ""
            if re.search(r"\/(etc|var|home)\/", line) or re.search(r"\b(credentials|passwd|shadow|ssh|\.env)\b", line):
                pass  # echter sensibler Pfad → CRITICAL bleibt
            else:
                f = replace(f, severity=Severity.MEDIUM)  # open(..., "w") ist normales Python
        if f.pattern_name in ("Remote Code Execution", "Shell Pipe Download", "Curl Pipe to Shell (LLM03)"):
            src_low = source.lower()
            if src_low.endswith((".yml", ".yaml", ".toml")):
                continue  # CI/Release-Doku (echo "curl ... | bash" in Publish-Steps)
            line = f.context or f.matched_text or ""
            if _QUOTE_CHARS_RE.search(line) and re.search(r"\b(evil|example|test|localhost|127\.0\.0\.1)\b", line, re.I):
                # Nur bei nachgewiesenem Test-/Doku-/Security-Tool-Kontext droppen.
                # Quotes + Platzhalter-Domain (evil.example.com) ist bei echten JSON-Payloads
                # (.mcp.json/package.json mit curl|bash) der Normalfall -> sonst CRITICAL False Negative.
                if _TEST_FILE_RE.search(source) or _is_readme_doc(source) \
                        or _SECURITY_TOOL_PATH_RE.search(source) or _TEST_CONTEXT_RE.search(line):
                    continue  # Teststring in Quotes (Paste-Protection-Tests)
        if f.pattern_name == "Toxic Flow - Data Exfiltration Chain" and "|" in (f.context or ""):
            continue  # Markdown-Tabellen-Zeile (Doku), keine Anweisung
        if f.pattern_name in ("Direct Override (EN/LLM01)", "Broad Ignore Instructions (EN)") and not is_doc:
            line = f.context or ""
            if line.lstrip().startswith(("//", "#", "--")):
                continue  # Code-Kommentar, kein Prompt
        if f.pattern_name in _ATTACK_TEST_PATTERNS:
            line = f.context or f.matched_text or ""
            if _TEST_CONTEXT_RE.search(line) or (
                _BLOCK_DESC_RE.search(line) and _QUOTE_CHARS_RE.search(line)
            ):
                continue  # Security-Tool: Testfall/Beschreibung der eigenen Abwehr, kein Angriff
        if f.pattern_name == "Sensitive File Access Request" and not is_instruction:
            line = f.context or f.matched_text or ""
            if line.lstrip().startswith(("//", "#", "--")):
                continue  # Code-Kommentar, keine Anweisung
            if _TEST_CONTEXT_RE.search(line) or (
                _BLOCK_DESC_RE.search(line) and _QUOTE_CHARS_RE.search(line)
            ):
                continue  # Security-Tool-Testfall/-Beschreibung, kein Angriff
        if f.category == "Output Injection" and not _COMMAND_VERBS.search(f.matched_text or ""):
            continue  # Backtick-False-Positive aus Doku/Kommentaren
        if is_js and f.pattern_name == "Backtick Command Substitution":
            continue  # Template-Literals sind keine Shell-Substitution
        if is_sh and f.pattern_name in (
            "Backtick Command Substitution",
            "Bash Command Substitution $(...)",
        ):
            continue  # Standard-Bash; Angriffsmuster sind separat abgedeckt
        if f.pattern_name in ("Email Address (LLM06)", "German Phone Number (LLM06)"):
            continue  # Kontaktangaben in Mod-Readmes sind normal
        if (
            f.pattern_name == "Sensitive File Access Request"
            and (_QUOTED_ENV_CMD.search(f.context or "") or _QUOTED_ENV_CMD.search(f.matched_text or ""))
        ):
            continue  # Zitat-Beispiel in Doku, keine Anweisung
        # --- v0.2-Phase-2: FP-Klassen der 10 neuen Corpus-Repos (19.10.) ---
        if f.pattern_name == "Suspicious open() in Agent Input":
            if not is_instruction:
                continue  # open() ist nur als ANWEISUNG in Instruktionsdateien ein Vektor; Code-IO und Doku-Codebeispiele sind normal
        if f.pattern_name == "Instruction Header Injection" and not is_instruction:
            continue  # "## Important Rules" in Doku/Output-Styles = Formatierung; nur Instruktionsdateien sind der Vektor
        if plain_doc and f.pattern_name in _PROMPT_DOC_FP_PATTERNS:
            continue  # Doku BESCHREIBT Extraktions-/Reset-Muster ("You can print...", "starts a new session") — echter Vektor nur in Instruktionsdateien
        if not is_doc and f.pattern_name == "Verification Bypass (ASI09)":
            continue  # "Skip confirmation prompt" als Feature-String in Code ist keine Injektion
        if not is_doc and f.pattern_name == "Approval Bypass (LLM08)":
            continue  # "auto-approve file reads" als Feature-/Beispielbeschreibung in Code; Vektor nur als Prompt-Anweisung
        if f.pattern_name in _ATTACK_TEST_PATTERNS and (f.context or "").lstrip().startswith(("#", "//", "--")):
            continue  # Kommentar beschreibt das eigene Muster ("# Example: ('rm -rf /', ..."), führt nichts aus
        if f.category == "Prompt Injection" and not is_doc and (f.context or "").lstrip().startswith(("#", "//", "--")):
            continue  # Prompt-Muster im Code-Kommentar = kein Injektionspfad
        if f.pattern_name == "Sensitive File Access Request" and re.search(r"#[^'\"]*(cat|source|read)\s+\.env", f.context or ""):
            continue  # Kommentar im eigenen Muster-Code ("# cat .env" im Sicherheits-Regex)
        if f.pattern_name == "Password in Cleartext" and re.search(r"\b(grep|rg|scan|search|find)\b.*password", f.context or "", re.I):
            continue  # Secret-Scanner-Skript sucht NACH Passwörtern (eigener Regex), enthält keins
        if f.pattern_name == "Secret Assignment" and re.search(r"PLACEHOLDER|__[A-Z_]+__", f.context or ""):
            continue  # Template-Platzhalter ("__PLACEHOLDER_THEME__"), kein Secret
        if f.pattern_name == "Package / Dependency Install" and not is_doc:
            f = replace(f, severity=Severity.LOW)  # pip/brew/yum in Setup-Skripten = Funktion; bösartige Installation läuft über URL-/Pipe-Muster (bleiben CRITICAL)
        if f.pattern_name == "IP Address in Sensitive Context (LLM06)":
            m = re.search(r"\b(0\.0\.0\.0|127\.\d+\.\d+\.\d+|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|::1|localhost)\b", f.matched_text or f.context or "")
            if m or plain_doc:
                continue  # private/loopback-Adressen und Doku-Erwähnungen sind keine sensiblen Funde
        if f.pattern_name == "Internal Network Probe" and plain_doc:
            continue  # Doku beschreibt Diagnose-Kommandos (ping/curl), führt sie nicht aus
        if f.pattern_name == "Exception Swallowing (ASI08)":
            line = (f.matched_text or "") + " " + (f.context or "")
            m = re.search(r"(?:except|catch)\s*(\([^)]*\)|[A-Za-z_.]+)", line)
            clause = m.group(1) if m else ""
            if clause and re.search(r"\b[A-Za-z_][\w.]*(Error|Expired|Warning)\b", clause) \
                    and not re.search(r"^\s*(Exception|BaseException)\s*$", clause):
                continue  # gezieltes Handling spezifischer Fehlertypen (optionale Dependencies) = Idiom, kein Swallowing
        if f.pattern_name == "Python subprocess/os.system":
            line = (f.matched_text or "") + " " + (f.context or "")
            dyn = bool(re.search(r"\{[^}]*[a-zA-Z_][^}]*\}|%\s*\(|%\s*[a-zA-Z_]|\+\s*(str\(|f['\"]|[a-zA-Z_])", line))
            if not dyn:
                f = replace(f, severity=Severity.LOW)  # statischer Aufruf (Liste oder fester String) = Tool-Alltag
            elif "os.system" not in (f.matched_text or "") and not re.search(r"shell\s*=\s*True", line):
                f = replace(f, severity=Severity.LOW)  # subprocess-Liste mit Variable: kein Shell-Interpreter
        out.append(f)
    return out


def detect_kind(root: Path) -> str:
    """Erkennt den Erweiterungs-Typ: mod (plugin.json), skill (SKILL.md), sonst generic."""
    if (root / "plugin.json").is_file():
        return "mod"
    if (root / "SKILL.md").is_file():
        return "skill"
    return "generic"



# ─── Kontext-Refiner (24.10., Corpus-Studie): Test-/Doku-/Security-Tool-/Echo-Kontexte ───
_TEST_FILE_RE = re.compile(
    r"(?:^|[/\\])(?:tests?|__tests__|__fixtures__|__mocks__|__snapshots__|fixtures|testdata|evals)(?:[/\\])"
    r"|(?:^|[/\\])test_[^/\\]+\.py$"
    r"|\.(?:test|spec)\.[a-z]+$", re.I)
_SECURITY_TOOL_PATH_RE = re.compile(
    r"(?:block-dangerous|guard-?pack|detect\.ts|scan_secrets|instructions-audit|protect-secrets|secret-box|security-)", re.I)
_REGEX_META_RE = re.compile(r"(?:\\[sdw]|\.\*|\(\?:|\[\^?[A-Za-z0-9_ -]+\])")
_NETWORK_EXFIL_RE = re.compile(
    r"(?:https?://|curl|wget|fetch\(|requests\.|urlopen|axios|socket|webhook|http\.request|\.post\(|pull\s+request|public\s+(?:repos?|repository|repositories))", re.I)
_ECHO_PREFIX_RE = re.compile(r"^\s*echo\s+", re.I)


_TEMPLATE_SECRET_RE = re.compile(r"(?:\{\{.*?\}\}|\$\{[^}]+\}|<[^>]*(?:your|placeholder|example|xxx)[^>]*>)", re.I)
_TEST_CARDS = frozenset({
    "4242424242424242", "4000000000000002", "5555555555554444", "5200828282828210",
    "5105105105105100", "378282246310005", "371449635398431", "6011111111111117",
    "6011000990139424", "4111111111111111", "4012888888881881", "4000056655665556",
    "4000002500003155", "4000000000009995", "4000000000009987", "4000000000009979",
    "4000000000000069", "4000000000000127", "4000000000000101", "4000000000000341",
    "4000000000003220", "4000000000003063", "4000000000003055",
})
_BENIGN_DUNDERS = frozenset({
    "__class__", "__name__", "__init__", "__doc__", "__file__", "__version__",
    "__dict__", "__module__", "__main__", "__qualname__", "__annotations__",
})


def _luhn_ok(digits: str) -> bool:
    if not digits.isdigit() or len(digits) < 12:
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _context_downgrade(findings: list[Finding], source: str = "", text: str = "") -> list[Finding]:
    """Kontext-Refiner: senkt Severity in bewiesenen FP-Kontexten (statt zu loeschen).
    Nur Luhn-Fail-Kreditkarten werden verworfen (eindeutige Geister)."""
    is_doc = source.endswith((".md", ".txt"))
    is_instruction = bool(_INSTRUCTION_FILE_RE.search(source))
    plain_doc = is_doc and not is_instruction
    is_test = bool(_TEST_FILE_RE.search(source))
    is_sec_tool = bool(_SECURITY_TOOL_PATH_RE.search(source))
    _lines = text.splitlines()
    out = []
    for f in findings:
        if f.pattern_name.startswith("Credit Card Number"):
            digits = re.sub(r"\D", "", f.matched_text or "")
            if not _luhn_ok(digits):
                continue  # Dezimalzahl, keine Karte (evals-Geister)
        # Template-Platzhalter sind keine hartcodierten Secrets ({{ var }}, ${var}, <your-key>)
        if f.pattern_name in ("Secret Assignment", "Hardcoded Secret") and _TEMPLATE_SECRET_RE.search(f.matched_text or ""):
            continue
        # Bekannte Test-Kreditkarten (Stripe/Braintree) sind keine echte PII
        if f.pattern_name.startswith("Credit Card Number"):
            if re.sub(r"\D", "", f.matched_text or "") in _TEST_CARDS:
                continue
        # Harmlose Dunder (__class__, __name__ ...) sind kein Sandbox-Ausbruch
        if f.pattern_name == "Python Magic Attributes" and (f.matched_text or "").strip() in _BENIGN_DUNDERS:
            continue
        # Doku (keine Instruktionsdatei): Secret-Beispiele + Python-Magic-Beispiele entfallen
        if plain_doc and f.pattern_name in ("Secret Assignment", "Hardcoded Secret", "Python Magic Attributes"):
            continue
        sev = f.severity
        # Doku-Prosa: Prompt-Injection-/Agentic-Behauptungen auf MEDIUM kappen (sichtbar bleiben)
        if plain_doc and f.category in ("Prompt Injection", "Agentic Security") and sev.score() >= Severity.HIGH.score():
            sev = Severity.MEDIUM
        if plain_doc and f.pattern_name.startswith("Toxic Flow"):
            continue  # Doku-Prosa: Wortkette ist keine Exfiltrations-Kette
        if is_test and sev.score() >= Severity.HIGH.score():
            sev = Severity.MEDIUM  # Test-/Eval-Dateien: Alarm kappen, sichtbar lassen
        if is_sec_tool and sev.score() >= Severity.HIGH.score():
            sev = Severity.MEDIUM  # Detektionslisten im Security-Tool selbst
        if f.category in ("Dangerous Command", "Data Exfiltration") and _REGEX_META_RE.search(f.matched_text or ""):
            if sev.score() > Severity.MEDIUM.score():
                sev = Severity.MEDIUM  # matched_text ist ein Regex-Muster, kein Befehl
        if f.category in ("Dangerous Command", "Mod Capability"):
            _ln = getattr(f, "line_number", 0)
            _orig = _lines[_ln - 1] if 0 < _ln <= len(_lines) else (f.context or "")
            if _ECHO_PREFIX_RE.match(_orig.strip()):
                sev = Severity.LOW  # Kommando wird nur ausgegeben, nicht ausgefuehrt
        if f.pattern_name.startswith("Toxic Flow") and not _NETWORK_EXFIL_RE.search((f.context or "") + " " + (f.matched_text or "")):
            sev = Severity.LOW  # Kein Netz-Indikator = keine Exfiltration (z. B. K8s-Probes)
        out.append(replace(f, severity=sev))
    return out


def scan_single_file(rel: str, text: str) -> list[Finding]:
    """Engine-Scan + Capability-Kombinationslogik für EINE Datei (genutzt von scan_mod und diff)."""
    findings: list[Finding] = []
    # 1) Engine-Scan (Prompt-Injection, Commands, Social Engineering)
    eng = scan_text(text, source=rel)
    findings.extend(eng.findings)
    # 1b) MCP-Manifest-Hinweis
    if rel.split("/")[-1] in (".mcp.json", "mcp.json", "mcp_config.json") and "mcpServers" in text:
        findings.append(Finding(
            severity=Severity.MEDIUM,
            category="MCP Config",
            pattern_name="MCP Manifest",
            matched_text="mcpServers",
            line_number=1,
            context=f"{rel}: MCP-Server-Konfiguration — Server-Quellen einzeln prüfen",
            recommendation="Prüfe jede mcpServers-Quelle (URL/Command) auf Vertrauenswürdigkeit.",
            confidence=90,
        ))
    # 1c) Committed Secrets (MCP08): .env-Dateien gehören nie in ein Mod
    if rel.split("/")[-1].endswith(".env") or ".env." in rel.split("/")[-1]:
        findings.append(Finding(
            severity=Severity.HIGH,
            category="MCP Config",
            pattern_name="Committed Env File",
            matched_text=rel.split("/")[-1],
            line_number=1,
            context=f"{rel}: .env-Datei im Mod — enthält evtl. echte Secrets",
            recommendation=".env nie committen; prüfen, ob die Datei echte Credentials enthält und aus dem Mod entfernen.",
            confidence=80,
        ))
    # 1d) Supply-Chain (MCP07): gefährliche package.json-Lifecycle-Skripte
    if rel.split("/")[-1] == "package.json" and "scripts" in text:
        for line_no, line in enumerate(text.splitlines(), 1):
            if re.search(r"\"(preinstall|install|postinstall|prepublish)\"\s*:\s*\"[^\"]*(curl|wget|sh\s|bash\s|rm\s+-rf|eval|base64)", line):
                findings.append(Finding(
                    severity=Severity.HIGH,
                    category="Supply Chain",
                    pattern_name="Dangerous npm Lifecycle Script",
                    matched_text=line.strip()[:160],
                    line_number=line_no,
                    context=f"{rel}: Lifecycle-Skript führt Shell-Befehle aus",
                    recommendation="pre/postinstall-Skripte laufen ungefragt bei Installation — genau prüfen, was sie tun.",
                    confidence=85,
                ))
    # 2) Angriffsprimitive: zeilenweise, feuern einzeln
    for line_no, line in enumerate(text.splitlines(), 1):
        for name, rx, sev, rec in ATTACK_PRIMITIVES:
            m = re.search(rx, line)
            if m:
                findings.append(Finding(
                    severity=sev,
                    category="Mod Capability",
                    pattern_name=name,
                    matched_text=m.group(0)[:160],
                    line_number=line_no,
                    context=line.strip()[:200],
                    recommendation=rec,
                    confidence=95,
                ))
    # 3) Capability-Inventar → Kombinationsregeln (mit Nähe-Kriterium)
    inv = _CapInv()
    for line_no, line in enumerate(text.splitlines(), 1):
        for marker, rx in CAPABILITY_MARKERS.items():
            if rx.search(line):
                first, _ = inv.markers.get(marker, (line_no, line_no))
                inv.markers[marker] = (first, line_no)
    for needed, name, sev, rec in COMBINATION_RULES:
        if needed <= set(inv.markers):
            lines = [inv.markers[m] for m in needed]
            first_line = min(l[0] for l in lines)
            span = max(l[1] for l in lines) - first_line
            if span > _MAX_MARKER_DISTANCE:
                continue  # Marker liegen weit auseinander → normale Mod-Struktur
            findings.append(Finding(
                severity=sev,
                category="Mod Capability",
                pattern_name=name,
                matched_text="+".join(sorted(needed)),
                line_number=first_line,
                context=f"{rel}: Kombination {' + '.join(sorted(needed))} gefunden (Zeilen {first_line}–{first_line + span})",
                recommendation=rec,
                confidence=75,
            ))
    # 4) A4-Mod-Detektoren (Prompt-Compose-Rewrite, Tool-Call-Rewrite, Update-Trojan)
    from .detectors_extra import scan_file as extra_scan
    findings.extend(extra_scan(rel, text))
    # Ein Refiner-Durchlauf über ALLE Findings (Engine + Primitive + Kombinationen)
    refined = _refine_code_findings(findings, rel)
    refined = _context_downgrade(refined, rel, text)  # Kontext-Refiner (24.10.)
    refined = _dedupe_cmd_line(refined)  # 1 Command-Finding je Zeile
    for f in refined:
        f.file = rel  # Evidenz-Zuordnung (21.10.): jedes Finding trägt seine Datei
        if not f.owasp_mcp:
            f.owasp_mcp = CATEGORY_OWASP_MCP.get(f.category, "")  # A5: OWASP-Mapping
    return refined


def scan_mod(root: Path, max_files: int | None = None) -> ScanReport:
    """Scannt einen Mod-/Skill-Ordner: Engine + Capability-Kombinationslogik, ein Report.
    max_files: optionaler Dateizahl-Cap (Benchmark-Schutz vor Riesen-Repos) —
    gecappte Scans werden im Report-Source markiert."""
    kind = detect_kind(root)
    files = discover_mod_files(root)
    capped = False
    if max_files is not None and len(files) > max_files:
        files = files[:max_files]
        capped = True
    findings: list[Finding] = []
    for p in files:
        rel = str(p.relative_to(root))
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        findings.extend(scan_single_file(rel, text))
    # Risk-Level aus der höchsten Einzel-Severity (nicht Summen-Overflow: sonst ist
    # jeder normale Mod CRITICAL, vgl. Benchmark FP ~100%)
    if findings:
        top = max(findings, key=lambda f: f.severity.score()).severity
        risk_score = top.score()
        risk_level = {
            Severity.LOW: "LOW",
            Severity.MEDIUM: "MEDIUM",
            Severity.HIGH: "HIGH",
            Severity.CRITICAL: "CRITICAL",
        }[top]
    else:
        risk_score = 0
        risk_level = "CLEAN"
    return ScanReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        source=f"{kind}:{root}" + (f" [capped: erste {max_files} Dateien]" if capped else ""),
        total_lines=0,
        total_findings=len(findings),
        risk_score=risk_score,
        risk_level=risk_level,
        findings=findings,
    )
