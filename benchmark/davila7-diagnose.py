# davila7-diagnose.py — findet die haengende Datei (Timeout pro Datei, eigenstaendiger Prozess)
import pathlib
import sys
import time

sys.path.insert(0, r"D:\AI-Labs\modvet")
from modvet.mods import scan_single_file

root = pathlib.Path(r"D:\AI-Labs\modvet\benchmark\corpus\davila7__claude-code-templates")
rel = sys.argv[1]
p = root / rel
text = p.read_text(encoding="utf-8", errors="replace")
print(f"Start: {rel} ({len(text)} Zeichen)", flush=True)
t0 = time.time()
findings = scan_single_file(rel, text)
print(f"FERTIG {time.time()-t0:.2f}s · {len(findings)} Findings", flush=True)
