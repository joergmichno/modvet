# corpus-study-generator.py — aggregiert rescan-2026-10-24 zu Statistik-Tabellen für die Corpus-Studie
import json
import pathlib
import collections

P = pathlib.Path(r"D:\AI-Labs\modvet\benchmark\rescan-2026-10-24")
rows = []
sev_total = collections.Counter()
cat_total = collections.Counter()
for f in sorted(P.glob("*.json")):
    if f.name in ("authors.json", "_summary.json"):
        continue
    d = json.loads(f.read_text(encoding="utf-8"))
    fs = d.get("findings", [])
    sev = collections.Counter(x["severity"] for x in fs)
    sev_total.update(sev)
    cat_total.update(x["category"] for x in fs)
    rows.append({
        "repo": f.stem,
        "n": len(fs),
        "crit": sev.get("CRITICAL", 0),
        "high": sev.get("HIGH", 0),
        "med": sev.get("MEDIUM", 0),
        "low": sev.get("LOW", 0),
        "risk": d.get("risk_level"),
        "lines": d.get("total_lines"),
    })

rows.sort(key=lambda r: -r["n"])
print(f"Repos: {len(rows)} · Findings gesamt: {sum(r['n'] for r in rows)}")
print("Severity gesamt:", dict(sev_total))
print("Kategorien:", dict(cat_total.most_common()))
print()
print("| Repo | Findings | CRIT | HIGH | MED | LOW | Risiko |")
print("|---|---|---|---|---|---|---|")
for r in rows:
    print(f"| {r['repo']} | {r['n']} | {r['crit']} | {r['high']} | {r['med']} | {r['low']} | {r['risk']} |")
