# hang-pattern.py — testet jede Pattern-Liste einzeln gegen die Problemdatei
import pathlib
import re
import sys
import time

sys.path.insert(0, r"D:\AI-Labs\modvet")
from modvet.core import engine

root = pathlib.Path(r"D:\AI-Labs\modvet\benchmark\corpus\davila7__claude-code-templates")
rel = sys.argv[1]
text = (root / rel).read_text(encoding="utf-8", errors="replace")
if len(sys.argv) > 2:
    text = text[: int(sys.argv[2])]

listen = [(name, getattr(engine, name)) for name in dir(engine)
          if name.isupper() and isinstance(getattr(engine, name), (list, tuple))]
print(f"{len(listen)} Pattern-Listen · Text {len(text)} Zeichen", flush=True)
for name, patterns in listen:
    t0 = time.time()
    for p in patterns:
        rx = p[0] if isinstance(p, (list, tuple)) else p
        if isinstance(rx, str):
            rx = re.compile(rx, re.IGNORECASE)
        rx.search(text)
    print(f"{time.time()-t0:7.2f}s · {name} ({len(patterns)})", flush=True)
print("ALLE OK", flush=True)
