#!/usr/bin/env python
# Perf-Profil: cProfile auf den langsamsten Scan (hesreallyhim, 68 Dateien)
# Usage: python tools/perf_profile.py [repo-slug] [top_n]
import cProfile, pstats, sys, io
from pathlib import Path

sys.path.insert(0, r"D:\AI-Labs\modvet")
from modvet.mods import scan_mod

repo = sys.argv[1] if len(sys.argv) > 1 else "hesreallyhim__awesome-claude-code"
top = int(sys.argv[2]) if len(sys.argv) > 2 else 25
root = Path(r"D:\AI-Labs\modvet\benchmark\corpus") / repo

prof = cProfile.Profile()
prof.enable()
report = scan_mod(root)
prof.disable()

s = io.StringIO()
ps = pstats.Stats(prof, stream=s).sort_stats("cumulative")
ps.print_stats(top)
print(f"=== {repo}: {report.total_findings} Findings, {report.risk_level} ===")
print(s.getvalue()[:6000])
with open(r"D:\AI-Labs\modvet\work-perf-profile.txt", "w", encoding="utf-8") as f:
    f.write(f"=== {repo} ===\n")
    f.write(s.getvalue())
print("vollständig: work-perf-profile.txt")
