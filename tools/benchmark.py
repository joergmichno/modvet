# tools/benchmark.py — Scannt das Corpus, misst Findings/Laufzeit, schreibt Tabelle
"""Usage: python tools/benchmark.py [--limit N]"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from modvet.mods import scan_mod  # noqa: E402

CORPUS = ROOT / "benchmark" / "corpus"
LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None

rows = []
cat_total = Counter()
for d in sorted(CORPUS.iterdir()):
    if not d.is_dir():
        continue
    if LIMIT and len(rows) >= LIMIT:
        break
    t0 = time.perf_counter()
    report = scan_mod(d)
    ms = (time.perf_counter() - t0) * 1000
    cats = Counter(f.category for f in report.findings)
    for c, n in cats.items():
        cat_total[c] += n
    rows.append({
        "slug": d.name,
        "files": len(list(d.rglob("*"))),
        "findings": report.total_findings,
        "risk": report.risk_level,
        "ms": round(ms, 1),
        "top_categories": dict(cats.most_common(3)),
    })

out = {
    "corpus_size": len(rows),
    "total_findings": sum(r["findings"] for r in rows),
    "avg_findings_per_repo": round(sum(r["findings"] for r in rows) / max(len(rows), 1), 1),
    "avg_ms": round(sum(r["ms"] for r in rows) / max(len(rows), 1), 1),
    "category_totals": dict(cat_total.most_common()),
    "rows": rows,
}
(ROOT / "benchmark" / "results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"REPOS: {len(rows)} | FINDINGS: {out['total_findings']} | Ø {out['avg_findings_per_repo']}/Repo | Ø {out['avg_ms']} ms")
print("\nKATEGORIEN:")
for c, n in cat_total.most_common(10):
    print(f"  {n:5d}  {c}")
print("\nJe Repo:")
for r in rows:
    print(f"  {r['slug']:45s} {r['findings']:4d} Findings  {r['risk']:8s} {r['ms']:8.1f} ms  {r['top_categories']}")
