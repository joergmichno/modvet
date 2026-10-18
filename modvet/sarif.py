#!/usr/bin/env python3
"""ModVet — SARIF-2.1.0-Export (stdlib only).

Wandelt einen ScanReport aus modvet/core/engine.py in ein
SARIF-2.1.0-konformes dict um. Keine externen Dependencies.
"""

from modvet.core.engine import Severity

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

# SARIF level: error/warning/note
_LEVELS = {
    Severity.CRITICAL: "error",
    Severity.HIGH: "error",
    Severity.MEDIUM: "warning",
    Severity.LOW: "note",
}


def format_sarif(report) -> dict:
    """ScanReport -> SARIF 2.1.0 dict.

    - tool.driver.name = "modvet"
    - eine rule je vorkommendem pattern_name (id = pattern_name)
    - ein result je Finding (level, message, location, modvetRiskLevel)
    """
    rules = []
    seen = set()
    for f in report.findings:
        if f.pattern_name not in seen:
            seen.add(f.pattern_name)
            rules.append({"id": f.pattern_name})

    results = []
    for f in report.findings:
        results.append(
            {
                "ruleId": f.pattern_name,
                "level": _LEVELS[f.severity],
                "message": {"text": f.recommendation or f.matched_text},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": report.source},
                            "region": {"startLine": f.line_number},
                        }
                    }
                ],
                "properties": {"modvetRiskLevel": f.severity.value},
            }
        )

    return {
        "version": "2.1.0",
        "$schema": SARIF_SCHEMA,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "modvet",
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }
