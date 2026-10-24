"""Vorher/Nachher-Messung Kontext-Refiner (24.10.)."""
import json, sys, time, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modvet.mods import scan_single_file

CORPUS = Path(r'D:\AI-Labs\modvet\benchmark\repos')
ALT = Path(r'D:\AI-Labs\modvet\benchmark\rescan-2026-10-24')
REPOS = sorted(p.stem for p in ALT.glob('*.json')
               if p.stem not in ('_summary', 'authors', 'davila7__claude-code-templates'))

for repo in REPOS:
    alt = json.loads((ALT / f'{repo}.json').read_text(encoding='utf-8'))
    alt_sev = collections.Counter(f['severity'] for f in alt.get('findings', []))
    neu_sev = collections.Counter()
    dateien = 0
    start = time.time()
    for datei in (CORPUS / repo).rglob('*'):
        if not datei.is_file():
            continue
        rel = str(datei.relative_to(CORPUS / repo)).replace('\\', '/')
        if any(t in rel for t in ['.git/', 'node_modules/', '__pycache__/', '.venv/', 'dist/', 'vendor/', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml']):
            continue
        try:
            if datei.stat().st_size > 500_000:
                continue
            text = datei.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue
        dateien += 1
        for f in scan_single_file(rel, text):
            neu_sev[f.severity.name] += 1
    alt_ges = sum(alt_sev.values())
    neu_ges = sum(neu_sev.values())
    print(f'{repo}:')
    print(f'  VORHER: {alt_ges} Findings · CRIT {alt_sev.get("CRITICAL",0)} HIGH {alt_sev.get("HIGH",0)} MED {alt_sev.get("MEDIUM",0)} LOW {alt_sev.get("LOW",0)}')
    print(f'  NACHHER: {neu_ges} Findings · CRIT {neu_sev.get("CRITICAL",0)} HIGH {neu_sev.get("HIGH",0)} MED {neu_sev.get("MEDIUM",0)} LOW {neu_sev.get("LOW",0)}')
    print(f'  ({dateien} Dateien, {time.time()-start:.0f}s)')
    sys.stdout.flush()
print('MESSUNG FERTIG')
