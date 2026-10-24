# hang-bisect.py — findet die haengende Zeile/Pattern per Halbierung (Timeout im Elternprozess)
import pathlib
import sys

sys.path.insert(0, r"D:\AI-Labs\modvet")
from modvet.mods import scan_single_file

root = pathlib.Path(r"D:\AI-Labs\modvet\benchmark\corpus\davila7__claude-code-templates")
rel = sys.argv[1]
start = int(sys.argv[2])
end = int(sys.argv[3])
lines = (root / rel).read_text(encoding="utf-8", errors="replace").split("\n")
teil = "\n".join(lines[start:end])
print(f"Zeilen {start}:{end} ({len(teil)} Zeichen)", flush=True)
scan_single_file(rel, teil)
print("OK", flush=True)
