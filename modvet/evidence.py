"""ModVet Evidenz-Report — maschinenlesbarer, reproduzierbarer Befund (21.10.2026).

Der Evidenz-Report beantwortet für einen externen Prüfer drei Fragen:
  1. WER hat gescannt (Scanner-Version) und MIT WELCHEN REGELN (Regelwerk-Hash)?
  2. WAS wurde gescannt (Datei-Manifest mit SHA-256)?
  3. WARUM kam welches Ergebnis zustande (jedes Finding mit Datei, Zeile, Muster)?

Deterministisch: gleicher Input + gleiche Regeln = gleicher Report-Inhalt
(der timestamp/invocation-Block ist bewusst getrennt, damit der
Befund-Teil hash-stabil bleibt).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .core import engine

RULESET_VERSION = "1.0"
EVIDENCE_VERSION = 1


def _norm(obj):
    """Normalisiert Sets/Tupel/Listen/Dicts zu hash-stabiler Form (Python-Hash-Seeds!)."""
    if isinstance(obj, (set, frozenset)):
        return sorted(_norm(x) for x in obj)
    if isinstance(obj, tuple):
        return [_norm(x) for x in obj]
    if isinstance(obj, list):
        return [_norm(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _norm(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    return obj


def _ruleset_payload() -> str:
    """Serialisiert die semantischen Regelwerks-Teile deterministisch."""
    from . import mods as mods_mod
    from . import detectors_extra

    csv = Path(engine.__file__).parent / "mapping-patterns.csv"
    parts = [
        _norm(engine.ALL_PATTERNS),
        _norm(engine.ALL_PATTERNS_BY_CATEGORY),
        _norm(mods_mod.COMBINATION_RULES),
        _norm(mods_mod._CMD_EXEC_PATTERNS),
        _norm(mods_mod._PROMPT_INJECTION_PATTERNS),
        _norm(mods_mod._ATTACK_TEST_PATTERNS),
        _norm(mods_mod._PROMPT_DOC_FP_PATTERNS),
        csv.read_text(encoding="utf-8", errors="replace"),
        # Detektor-Quelle (Muster liegen inline in scan_file)
        Path(detectors_extra.__file__).read_text(encoding="utf-8", errors="replace"),
    ]
    return json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)


def ruleset_fingerprint() -> str:
    """SHA-256 über das effektive Regelwerk — gleiche Regeln, gleicher Hash."""
    return hashlib.sha256(_ruleset_payload().encode("utf-8")).hexdigest()


def build_evidence_report(root: Path, report, argv: list[str] | None) -> dict:
    """Baut den Evidenz-Report als Dict (Befund-Teil deterministisch)."""
    manifest = {}
    total_lines = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        try:
            rel = str(p.relative_to(root)).replace("\\", "/")
            data = p.read_bytes()
            manifest[rel] = {
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
            if rel.endswith((".py", ".js", ".ts", ".md", ".json", ".yaml", ".yml", ".toml", ".sh", ".txt", ".csv")):
                total_lines += data.count(b"\n") + 1
        except OSError:
            continue

    findings = [
        {
            "severity": f.severity.value,
            "category": f.category,
            "rule": f.pattern_name,
            "file": f.file,
            "line_number": f.line_number,
            "matched_text": f.matched_text,
            "context": f.context,
            "recommendation": f.recommendation,
            "confidence": f.confidence,
            "owasp_mcp": f.owasp_mcp,
        }
        for f in report.findings
    ]

    # Befund-Teil: deterministisch (sort_keys) — hash-stabil
    body = {
        "evidence_version": EVIDENCE_VERSION,
        "scanner": {"name": "modvet", "version": __version__},
        "ruleset": {
            "version": RULESET_VERSION,
            "fingerprint_sha256": ruleset_fingerprint(),
        },
        "target": {
            "path": str(root),
            "files_scanned": len(manifest),
            "total_lines": total_lines,
            "manifest": manifest,
        },
        "result": {
            "total_findings": len(findings),
            "risk_level": report.risk_level,
            "risk_score": report.risk_score,
            "findings": findings,
        },
    }
    return {
        "meta": {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "invocation": {"argv": argv or sys.argv, "python": sys.version.split()[0]},
        },
        "evidence": body,
        "evidence_body_sha256": hashlib.sha256(
            json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
    }


def write_evidence_report(root: Path, report, out: Path, argv: list[str] | None) -> Path:
    data = build_evidence_report(root, report, argv)
    out.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    return out
