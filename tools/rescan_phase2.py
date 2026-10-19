#!/usr/bin/env python
# Phase-2-Re-Scan: 6 Hotspot-Repos mit aktuellem Code-Stand scannen (CLI-Pfad)
import json, subprocess, sys, time
from pathlib import Path

ROOT = Path(r"D:\AI-Labs\modvet\benchmark\corpus")
REPOS = [
    "disler__claude-code-hooks-mastery",
    "disler__claude-code-hooks-multi-agent-observability",
    "zenbu-labs__terminal-browser",
    "es617__claude-replay",
    "wshobson__agents",
    "akin-ozer__cc-devops-skills",
]
t0 = time.time()
out = []
for name in REPOS:
    p = ROOT / name
    r = subprocess.run(
        [sys.executable, "-c", "from modvet.cli import main; main()",
         "scan", str(p), "--json"],
        capture_output=True, text=True, timeout=900, cwd=r"D:\AI-Labs\modvet",
    )
    try:
        d = json.loads(r.stdout)
        row = {
            "repo": name,
            "findings": d.get("total_findings"),
            "risk": d.get("risk_level"),
            "cats": {},
            "sev": {},
        }
        import collections
        row["cats"] = dict(collections.Counter(f["category"] for f in d.get("findings", [])))
        row["sev"] = dict(collections.Counter(f["severity"] for f in d.get("findings", [])))
    except Exception as e:
        row = {"repo": name, "error": str(e), "stdout_tail": r.stdout[-300:], "stderr_tail": r.stderr[-300:]}
    out.append(row)
    print(f"{name}: {row.get('findings', 'ERR')} Findings, risk={row.get('risk')}, {time.time()-t0:.0f}s", flush=True)

with open(r"D:\AI-Labs\modvet\work-rescan-phase2.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("FERTIG -> work-rescan-phase2.json")
