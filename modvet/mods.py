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

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import re

from .core.engine import Finding, ScanReport, Severity, scan_text

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
_DOC_DIR_RE = re.compile(r"(^|/)(docs?|examples?)/", re.I)

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
        out.append(f)
    return out


def detect_kind(root: Path) -> str:
    """Erkennt den Erweiterungs-Typ: mod (plugin.json), skill (SKILL.md), sonst generic."""
    if (root / "plugin.json").is_file():
        return "mod"
    if (root / "SKILL.md").is_file():
        return "skill"
    return "generic"


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
    # Ein Refiner-Durchlauf über ALLE Findings (Engine + Primitive + Kombinationen)
    return _refine_code_findings(findings, rel)


def scan_mod(root: Path) -> ScanReport:
    """Scannt einen Mod-/Skill-Ordner: Engine + Capability-Kombinationslogik, ein Report."""
    kind = detect_kind(root)
    findings: list[Finding] = []
    for p in discover_mod_files(root):
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
        source=f"{kind}:{root}",
        total_lines=0,
        total_findings=len(findings),
        risk_score=risk_score,
        risk_level=risk_level,
        findings=findings,
    )
