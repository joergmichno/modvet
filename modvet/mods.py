"""ModVet — Mod-Discovery + Capability-Scanning für Claude-Code-Mods.

Zwei Schichten:
1. Engine-Scan (modvet.core.engine): Prompt-Injection / Dangerous-Commands / Social-Engineering
   auf allen Textdateien eines Mods.
2. Capability-Scan: statische Muster für gefährliche Mod-Fähigkeiten
   (Shell-Exec, Exfiltration, Env-/File-Zugriff, Hook-Permission-Lift).
Deterministisch, offline, kein LLM.
"""
from __future__ import annotations

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

# (name, regex, severity, recommendation)
CAPABILITY_PATTERNS: list[tuple[str, str, Severity, str]] = [
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
        "Process Exec",
        r"(child_process|execSync|spawnSync|\bspawn\s*\(|\bexec\s*\(|\bshelljs\b|os\.system\b)",
        Severity.HIGH,
        "Spawns OS processes — review what runs and with which input.",
    ),
    (
        "Network POST (Exfil-Pfad)",
        r"method\s*:\s*['\"]POST['\"]",
        Severity.HIGH,
        "Sends HTTP POST — check whether payload contains secrets or local data.",
    ),
    (
        "Config Rewrite",
        r"(claude\.json|settings\.json|\.claude)[^\n]{0,80}(writeFile|appendFile|write\(|override|replace)",
        Severity.HIGH,
        "Modifies Claude configuration files at runtime.",
    ),
    (
        "Env Read",
        r"(process\.env|import\.meta\.env|\.env\.get\b)",
        Severity.MEDIUM,
        "Reads environment variables — secrets exposure risk if combined with network.",
    ),
    (
        "File Write",
        r"(fs\.writeFile|fs\.appendFile|writeFileSync|appendFileSync|fs\.write\s*\()",
        Severity.MEDIUM,
        "Writes files — review paths (jail/path-traversal risk).",
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


def _severity_from_score(score: int) -> str:
    if score >= 30:
        return "CRITICAL"
    if score >= 10:
        return "HIGH"
    if score > 0:
        return "LOW"
    return "CLEAN"


# FP-Reduktion: "Command Injection in Output" feuert auch auf Backticks in
# Code-Doku (`` `ps -axo ...` ``). Nur behalten, wenn der Match tatsächlich
# nach Kommando aussieht (Kommando-Verb enthalten).
_COMMAND_VERBS = re.compile(
    r"(?i)\b(ps|ls|cat|rm|curl|wget|npm|npx|git|bash|sh|python3?|chmod|chown|sudo|nc|ssh|find|grep)\b"
)


def _refine_code_findings(findings: list[Finding]) -> list[Finding]:
    out = []
    for f in findings:
        if f.category == "Output Injection" and not _COMMAND_VERBS.search(f.matched_text or ""):
            continue  # Backtick-False-Positive aus Doku/Kommentaren
        out.append(f)
    return out


def detect_kind(root: Path) -> str:
    """Erkennt den Erweiterungs-Typ: mod (plugin.json), skill (SKILL.md), sonst generic."""
    if (root / "plugin.json").is_file():
        return "mod"
    if (root / "SKILL.md").is_file():
        return "skill"
    return "generic"


def scan_mod(root: Path) -> ScanReport:
    """Scannt einen Mod-/Skill-Ordner: Engine + Capability-Patterns, ein konsolidierter Report."""
    kind = detect_kind(root)
    findings: list[Finding] = []
    for p in discover_mod_files(root):
        rel = str(p.relative_to(root))
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # 1) Engine-Scan (Prompt-Injection, Commands, Social Engineering)
        eng = scan_text(text, source=rel)
        findings.extend(_refine_code_findings(eng.findings))
        # 1b) MCP-Manifest-Hinweis (Skill-/Agent-Konfigurationen)
        if p.name in (".mcp.json", "mcp.json", "mcp_config.json") and "mcpServers" in text:
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
        # 2) Capability-Scan mit Zeilennummern
        for line_no, line in enumerate(text.splitlines(), 1):
            for name, rx, sev, rec in CAPABILITY_PATTERNS:
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
    total_score = sum(f.severity.score() for f in findings)
    return ScanReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        source=f"{kind}:{root}",
        total_lines=0,
        total_findings=len(findings),
        risk_score=total_score,
        risk_level=_severity_from_score(total_score),
        findings=findings,
    )
