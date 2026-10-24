# hang-stages.py — misst jede Pipeline-Stufe einzeln gegen die Problemdatei
import pathlib
import sys
import time

sys.path.insert(0, r"D:\AI-Labs\modvet")
from modvet.core.engine import scan_text
from modvet import mods

root = pathlib.Path(r"D:\AI-Labs\modvet\benchmark\corpus\davila7__claude-code-templates")
rel = sys.argv[1]
text = (root / rel).read_text(encoding="utf-8", errors="replace")

t0 = time.time()
rep = scan_text(text, source=rel)
print(f"1) scan_text: {time.time()-t0:.2f}s · {len(rep.findings)} Findings", flush=True)

t0 = time.time()
n = 0
for line in text.splitlines():
    for name, rx, sev, rec in mods.ATTACK_PRIMITIVES:
        import re
        if re.search(rx, line):
            n += 1
print(f"2) ATTACK_PRIMITIVES: {time.time()-t0:.2f}s · {n}", flush=True)

t0 = time.time()
inv = mods._CapInv()
for line_no, line in enumerate(text.splitlines(), 1):
    for marker, rx in mods.CAPABILITY_MARKERS.items():
        if rx.search(line):
            first, _ = inv.markers.get(marker, (line_no, line_no))
            inv.markers[marker] = (first, line_no)
print(f"3) CAPABILITY_MARKERS: {time.time()-t0:.2f}s", flush=True)

t0 = time.time()
from modvet.detectors_extra import scan_file as extra_scan
extra = extra_scan(rel, text)
print(f"4) detectors_extra: {time.time()-t0:.2f}s · {len(extra)}", flush=True)

t0 = time.time()
refined = mods._refine_code_findings(rep.findings + extra, rel)
print(f"5) _refine_code_findings: {time.time()-t0:.2f}s · {len(refined)}", flush=True)
print("ALLE STUFEN OK", flush=True)
