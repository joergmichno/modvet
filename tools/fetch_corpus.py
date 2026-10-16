# tools/fetch_corpus.py — Benchmark-Corpus: echte Mod-Repos von GitHub laden (read-only)
"""Liest awesome-claude-code-mods-Katalog, lädt bis N Mod-Repos als Tarballs,
extrahiert nach benchmark/corpus/<owner>__<repo>/ und schreibt corpus.json."""
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "benchmark" / "corpus"
CATALOG_URL = "https://raw.githubusercontent.com/karanb192/awesome-claude-code-mods/main/README.md"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 15

CORPUS.mkdir(parents=True, exist_ok=True)
req = urllib.request.Request(CATALOG_URL, headers={"User-Agent": "modvet-benchmark/0.2"})
text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

# GitHub-Links: github.com/owner/repo (ohne /tree/, /blob/, /issues etc.)
links = re.findall(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", text)
seen, repos = set(), []
for owner, repo in links:
    key = f"{owner}/{repo}".lower()
    if key in seen or repo.endswith(("awesome", "list", "catalog", "mods")):
        continue
    seen.add(key)
    repos.append((owner, repo))

meta = []
for owner, repo in repos[:N]:
    slug = f"{owner}__{repo}"
    dest = CORPUS / slug
    if dest.exists():
        meta.append({"slug": slug, "owner": owner, "repo": repo, "cached": True})
        continue
    url = f"https://codeload.github.com/{owner}/{repo}/tar.gz/refs/heads/main"
    tgz = CORPUS / f"{slug}.tar.gz"
    try:
        subprocess.run(
            ["curl", "-sL", "--max-time", "60", "-o", str(tgz), url],
            check=True, capture_output=True,
        )
        subprocess.run(["tar", "-xzf", str(tgz), "-C", str(CORPUS)], check=True)
        tgz.unlink(missing_ok=True)
        # tar entpackt als <repo>-main/ → umbenennen
        extracted = CORPUS / f"{repo}-main"
        if extracted.exists():
            extracted.rename(dest)
        else:  # Fallback: master-Branch
            subprocess.run(
                ["curl", "-sL", "--max-time", "60", "-o", str(tgz),
                 f"https://codeload.github.com/{owner}/{repo}/tar.gz/refs/heads/master"],
                check=True, capture_output=True,
            )
            subprocess.run(["tar", "-xzf", str(tgz), "-C", str(CORPUS)], check=True)
            tgz.unlink(missing_ok=True)
            (CORPUS / f"{repo}-master").rename(dest)
        meta.append({"slug": slug, "owner": owner, "repo": repo, "cached": False})
        print(f"OK {slug}")
    except Exception as e:
        print(f"FAIL {slug}: {e}")
        tgz.unlink(missing_ok=True)

(CORPUS / "corpus.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print(f"\nCORPUS: {len(meta)} Repos in {CORPUS}")
