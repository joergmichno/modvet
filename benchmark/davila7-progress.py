# davila7-progress.py — scannt alle Dateien einzeln mit Fortschritt + Slow-Log (findet weitere Haenger)
import json
import pathlib
import sys
import time

sys.path.insert(0, r"D:\AI-Labs\modvet")
from modvet.mods import discover_mod_files, scan_single_file

root = pathlib.Path(r"D:\AI-Labs\modvet\benchmark\corpus\davila7__claude-code-templates")
out = pathlib.Path(r"D:\AI-Labs\modvet\benchmark\rescan-2026-10-24")
files = list(discover_mod_files(root))
print(f"{len(files)} Dateien", flush=True)
alle = []
langsam = []
t_start = time.time()
for i, p in enumerate(files):
    rel = str(p.relative_to(root)).replace("\\", "/")
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    t0 = time.time()
    fs = scan_single_file(rel, text)
    dt = time.time() - t0
    if dt > 3:
        langsam.append({"file": rel, "s": round(dt, 1), "kb": len(text) // 1024})
        print(f"LANGSAM {dt:.1f}s · {len(text)//1024} KB · {rel}", flush=True)
    for f in fs:
        f.file = rel
    alle.extend(fs)
    if (i + 1) % 500 == 0:
        print(f"{i+1}/{len(files)} · {time.time()-t_start:.0f}s · {len(alle)} Findings", flush=True)

(out / "davila7-slow.json").write_text(json.dumps(langsam, indent=2), encoding="utf-8")
print(f"FERTIG: {len(alle)} Findings · {time.time()-t_start:.0f}s · {len(langsam)} langsame Dateien", flush=True)
