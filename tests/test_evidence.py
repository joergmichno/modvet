"""ModVet Evidenz-Report-Tests (21.10.) — deterministischer Befund mit Regelwerk-Hash."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
CLI = [PY, "-m", "modvet.cli"]
FIX = ROOT / "tests" / "fixtures"


def run(args, cwd=ROOT):
    return subprocess.run(
        CLI + args, cwd=str(cwd), capture_output=True, text=True, timeout=180
    )


def test_evidence_report_structure():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "evidence.json"
        r = run(["scan", str(FIX / "malicious-mod"), "--evidence", str(out)])
        assert out.exists(), f"Report fehlt: stderr={r.stderr}"
        data = json.loads(out.read_text(encoding="utf-8"))
        ev = data["evidence"]
        assert ev["scanner"]["name"] == "modvet"
        assert ev["scanner"]["version"], "Scanner-Version leer"
        fp = ev["ruleset"]["fingerprint_sha256"]
        assert len(fp) == 64 and all(c in "0123456789abcdef" for c in fp), fp
        assert ev["ruleset"]["version"] == "1.0"
        assert ev["target"]["files_scanned"] > 0
        assert all(v["sha256"] for v in ev["target"]["manifest"].values())
        # Jedes Finding trägt Datei + Zeile + Regel
        assert ev["result"]["total_findings"] > 0, "malicious-mod muss Findings haben"
        for f in ev["result"]["findings"]:
            assert f["file"], "Finding ohne file-Zuordnung"
            assert isinstance(f["line_number"], int) and f["line_number"] >= 0
            assert f["rule"]
        assert data["evidence_body_sha256"]
        print("PASS evidence-structure")


def test_evidence_deterministic():
    """Gleicher Input + gleiche Regeln => identischer Befund-Body (Hash-stabil)."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        out1, out2 = td / "a.json", td / "b.json"
        run(["scan", str(FIX / "malicious-mod"), "--evidence", str(out1)])
        run(["scan", str(FIX / "malicious-mod"), "--evidence", str(out2)])
        d1 = json.loads(out1.read_text(encoding="utf-8"))
        d2 = json.loads(out2.read_text(encoding="utf-8"))
        assert d1["evidence"] == d2["evidence"], "Befund-Teil nicht deterministisch"
        assert d1["evidence_body_sha256"] == d2["evidence_body_sha256"]
        print("PASS evidence-deterministic")


def test_evidence_clean_mod():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "evidence.json"
        r = run(["scan", str(FIX / "clean-mod"), "--evidence", str(out)])
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["evidence"]["result"]["total_findings"] == 0
        assert data["evidence"]["result"]["risk_level"] == "CLEAN"
        print("PASS evidence-clean-mod")


def test_json_report_has_file_field():
    r = run(["scan", str(FIX / "malicious-mod"), "--json"])
    rep = json.loads(r.stdout)
    assert "modvet_version" in rep and rep["modvet_version"], "modvet_version fehlt"
    assert all(f["file"] for f in rep["findings"]), "JSON-Findings ohne file"
    print("PASS json-file-field")


if __name__ == "__main__":
    for fn in sorted(k for k in globals() if k.startswith("test_")):
        try:
            globals()[fn]()
        except Exception:
            print(f"FAIL {fn}")
            raise
    print("ALL EVIDENCE TESTS PASS")
