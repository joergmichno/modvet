# rescan-distribution.py — Corpus-Re-Scan mit ModVet 0.2.4 für evidenzbasierte Outreach-Vorbereitung
import json
import subprocess
import time
import pathlib

ROOT = pathlib.Path(r"D:\AI-Labs\modvet")
OUT = ROOT / "benchmark" / "rescan-2026-10-24"
OUT.mkdir(exist_ok=True)
CLI = r"D:\tmp\modvet-verify\Scripts\modvet.exe"

summary = []
for repo in sorted((ROOT / "benchmark" / "corpus").iterdir()):
    if not repo.is_dir():
        continue
    ziel = OUT / (repo.name + ".json")
    t0 = time.time()
    try:
        r = subprocess.run([CLI, "scan", str(repo), "--json"], capture_output=True, text=True, timeout=600)
        ziel.write_text(r.stdout, encoding="utf-8")
        d = json.loads(r.stdout)
        n = len(d.get("findings", []))
        summary.append({"repo": repo.name, "findings": n, "risk": d.get("risk"), "s": round(time.time() - t0, 1)})
        print(f"{repo.name}: {n} Findings · risk={d.get('risk')} · {round(time.time()-t0,1)}s", flush=True)
    except Exception as e:
        summary.append({"repo": repo.name, "error": str(e)[:200]})
        print(f"{repo.name}: FEHLER {str(e)[:150]}", flush=True)

(OUT / "_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print("FERTIG:", len(summary), "Repos")
