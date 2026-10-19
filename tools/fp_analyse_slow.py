#!/usr/bin/env python
# FP-Analyse Teil 2 (langsame Repos) — gleiche Logik, anderer Output
import sys, json, time
from pathlib import Path

sys.path.insert(0, r"D:\AI-Labs\modvet")
from modvet.mods import scan_single_file

ROOT = Path(r"D:\AI-Labs\modvet\benchmark\corpus")
REPOS = [
    "es617__claude-replay",
    "wshobson__agents",
    "akin-ozer__cc-devops-skills",
]
MAX_FILES = 500
SKIP_DIRS = {".git", "node_modules", "__pycache__", "dist", ".venv", "venv"}

out = []
t0 = time.time()
for name in REPOS:
    root = ROOT / name
    files = [p for p in sorted(root.rglob("*"))
             if p.is_file() and not (set(p.parts) & SKIP_DIRS)]
    files = files[:MAX_FILES]
    for p in files:
        rel = str(p.relative_to(root)).replace("\\", "/")
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for f in scan_single_file(rel, text):
            out.append({
                "repo": name,
                "file": rel,
                "category": str(f.category),
                "pattern": f.pattern_name,
                "severity": str(f.severity),
                "line": f.line_number,
                "ctx": (f.context or "")[:160],
            })
    print(f"{name}: fertig, {time.time()-t0:.0f}s", flush=True)

with open(r"D:\AI-Labs\modvet\work-fp-analyse-slow.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
print("GESAMT:", len(out), "-> work-fp-analyse-slow.json")
