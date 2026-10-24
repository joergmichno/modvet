# hang-timing.py — findet das langsame Pattern (finditer auf der Problemzeile)
import pathlib
import sys
import time

sys.path.insert(0, r"D:\AI-Labs\modvet")
from modvet.core import engine

root = pathlib.Path(r"D:\AI-Labs\modvet\benchmark\corpus\davila7__claude-code-templates")
rel = sys.argv[1]
text = (root / rel).read_text(encoding="utf-8", errors="replace")
line = text.splitlines()[0] if text.splitlines() else text
print(f"Zeile: {len(line)} Zeichen · _COMBINED_MAX_LEN={engine._COMBINED_MAX_LEN}", flush=True)

# Quick-Reject-Kategorien wie im Original
active = {cat for cat, rx in engine._COMBINED_BY_CATEGORY.items() if rx is not None and rx.search(line)}
active.update(cat for cat, rx in engine._COMBINED_BY_CATEGORY.items() if rx is None)
print("Aktive Kategorien:", sorted(active), flush=True)

langsam = []
for name, compiled, severity, category, recommendation in engine.COMPILED_PATTERNS:
    if category not in active:
        continue
    t0 = time.time()
    n = 0
    for m in compiled.finditer(line):
        n += 1
        if n > 100000:
            break
    dt = time.time() - t0
    if dt > 0.3:
        langsam.append((dt, name, category, n))
        print(f"{dt:8.2f}s · {name} ({category}) · {n} Matches", flush=True)
print("FERTIG", flush=True)
