# hang-variants.py — misst die Kosten jeder Normalisierungs-Variante auf der Problemzeile
import pathlib
import sys
import time

sys.path.insert(0, r"D:\AI-Labs\modvet")
from modvet.core import engine

root = pathlib.Path(r"D:\AI-Labs\modvet\benchmark\corpus\davila7__claude-code-templates")
rel = sys.argv[1]
line = (root / rel).read_text(encoding="utf-8", errors="replace").splitlines()[0]

varianten = {"original": line}
t0 = time.time()
varianten["reverse"] = engine._reverse_text(line)
print(f"reverse erzeugt: {time.time()-t0:.2f}s", flush=True)
t0 = time.time()
if engine._BASE64_CANDIDATE_RE.search(line):
    varianten["base64"] = engine._decode_base64_fragments(line)
print(f"base64 erzeugt: {time.time()-t0:.2f}s", flush=True)
t0 = time.time()
if engine._HAS_MARKUP_RE.search(line):
    varianten["md"] = engine._strip_markdown(line)
print(f"markdown erzeugt: {time.time()-t0:.2f}s", flush=True)

for vname, vtext in varianten.items():
    t0 = time.time()
    n = 0
    for name, compiled, severity, category, recommendation in engine.COMPILED_PATTERNS:
        for m in compiled.finditer(vtext):
            n += 1
    print(f"{time.time()-t0:8.2f}s · Variante {vname} ({len(vtext)} Zeichen) · {n} Matches", flush=True)
