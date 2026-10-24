"""Tests für den Kontext-Refiner (24.10., Corpus-FP-Klassen)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modvet.mods import scan_single_file
from modvet.core.engine import Severity


def _finde(rel, text, pattern_prefix=None):
    fs = scan_single_file(rel, text)
    if pattern_prefix:
        fs = [f for f in fs if f.pattern_name.startswith(pattern_prefix)]
    return fs


def test_kreditkarte_geist_wird_verworfen():
    fs = _finde("evals/static-score-snapshot.json",
                '{"static_score": 0.5599999999999999, "token_efficiency": 0.9820}',
                "Credit Card Number")
    assert fs == [], f"Geister-Karte sollte verworfen werden: {fs}"


def test_kreditkarte_echt_bleibt_critical():
    fs = _finde("config/customer.json",
                '{"card": "4111111111111111"}',
                "Credit Card Number")
    assert len(fs) >= 1
    assert fs[0].severity == Severity.CRITICAL


def test_testdatei_wird_gekappt_nicht_geloescht():
    fs = _finde("tests/skill-conventions.test.ts",
                'const beispiel = "```bash\\nrm -rf /\\n```";',
                "Destructive Shell Command")
    assert len(fs) >= 1
    assert all(f.severity == Severity.MEDIUM for f in fs), fs


def test_echo_ist_kein_rce():
    fs = _finde("scripts/install_tools.sh",
                'echo "    curl --proto \'=https\' --tlsv1.2 -sSf https://raw.githubusercontent.com/nektos/act/master/install.sh | bash -s -- -b ~/bin/act"')
    relevant = [f for f in fs if f.category in ("Dangerous Command", "Mod Capability")]
    assert len(relevant) >= 1, f"Echo-Kommando sollte als LOW sichtbar bleiben: {fs}"
    assert all(f.severity == Severity.LOW for f in relevant), relevant


def test_k8s_probe_ist_keine_exfiltration():
    fs = _finde("examples/statefulset.yaml",
                'readinessProbe:\n  exec:\n    command: ["pg_isready", "-U", "postgres"]',
                "Toxic Flow")
    assert all(f.severity == Severity.LOW for f in fs), fs


def test_security_tool_eigencode_wird_gekappt():
    fs = _finde("plugins/block-dangerous-commands/block-dangerous-commands.js",
                'const patterns = ["mkfs", "dd if=/dev/zero"];',
                "Destructive Shell Command")
    assert all(f.severity == Severity.MEDIUM for f in fs), fs


def test_echter_rce_bleibt_critical():
    fs = _finde("cli/src/upgrade.ts",
                'const child = spawn("bash", ["-c", `curl -fsSL \'${url}\' | bash`], { stdio: "inherit" });',
                "Remote Code Execution")
    assert len(fs) >= 1, "Echter RCE darf nicht verworfen werden"
    assert fs[0].severity == Severity.CRITICAL, fs[0]


def test_doku_toxic_flow_wird_verworfen():
    fs = _finde("docs/plans/beispiel.md",
                'The pipeline will read the plan body from disk and send it as the issue markdown.',
                "Toxic Flow")
    assert fs == [], f"Doku-Toxic-Flow sollte entfallen: {fs}"
