"""ModVet CLI — `modvet scan` / `modvet snapshot` / `modvet diff`.

Exit-Codes: 0 = clean, 1 = Findings >= --fail-on, 2 = usage/error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .core.engine import Severity, format_human, format_json
from .mods import discover_mod_files, scan_mod

SNAPSHOT_VERSION = 1


def _manifest(root: Path) -> dict:
    out = {}
    for p in discover_mod_files(root):
        rel = str(p.relative_to(root)).replace("\\", "/")
        try:
            data = p.read_bytes()
        except OSError:
            continue
        out[rel] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    return out


def cmd_scan(args: argparse.Namespace) -> int:
    root = Path(args.path)
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    report = scan_mod(root)
    if getattr(args, "format", "human") == "sarif":
        from .sarif import format_sarif
        print(json.dumps(format_sarif(report), indent=2, ensure_ascii=False))
    elif args.json:
        print(format_json(report))
    else:
        print(format_human(report))
    threshold = Severity[args.fail_on.upper()].score()
    return 1 if any(f.severity.score() >= threshold for f in report.findings) else 0


def cmd_badge(args: argparse.Namespace) -> int:
    from .badge import badge_svg
    src = Path(args.input)
    try:
        rep = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: report unreadable: {e}", file=sys.stderr)
        return 2
    level = rep.get("risk_level", "UNKNOWN")
    findings = int(rep.get("total_findings", 0))
    svg = badge_svg(level, findings)
    out = Path(args.out) if args.out else Path("badge.svg")
    out.write_text(svg, encoding="utf-8")
    print(f"badge: {level} ({findings} findings) -> {out}")
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    root = Path(args.path)
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    snap = {"version": SNAPSHOT_VERSION, "files": _manifest(root)}
    out = Path(args.out) if args.out else Path(".modvet-snapshot.json")
    out.write_text(json.dumps(snap, indent=2, sort_keys=True), encoding="utf-8")
    print(f"snapshot: {len(snap['files'])} files -> {out}")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    root = Path(args.path)
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    try:
        snap = json.loads(Path(args.against).read_text(encoding="utf-8"))
        old = snap["files"]
    except (OSError, KeyError, json.JSONDecodeError) as e:
        print(f"error: snapshot unreadable: {e}", file=sys.stderr)
        return 2
    new = _manifest(root)
    changed = sorted(set(new) - set(old))
    changed += [f for f in sorted(set(new) & set(old)) if new[f]["sha256"] != old[f]["sha256"]]
    removed = sorted(set(old) - set(new))
    print("=== Update-Delta ===")
    for f in changed:
        print(f"  CHANGED  {f}")
    for f in removed:
        print(f"  REMOVED  {f}")
    if not changed and not removed:
        print("  (kein Delta — installierte Version identisch mit Snapshot)")
        return 0
    # Findings nur auf geänderten/neuen Dateien
    findings = []
    for rel in changed:
        p = root / rel
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        findings.extend(scan_mod_report_on_single_file(rel, text))
    if findings:
        print(f"=== Delta-Findings ({len(findings)}) ===")
        for f in findings:
            print(f"  [{f.severity.value}] {f.pattern_name} ({f.category}) {f.line_number}: {f.matched_text[:80]}")
    else:
        print("  Delta-Findings: keine")
    threshold = Severity[args.fail_on.upper()].score()
    return 1 if any(f.severity.score() >= threshold for f in findings) else 0


def scan_mod_report_on_single_file(rel: str, text: str):
    """Engine-Scan + Capability-Kombinationslogik für genau eine Datei (Delta-Pfad)."""
    from .mods import scan_single_file
    return scan_single_file(rel, text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="modvet", description="ModVet — pre-install security scanner for Claude Code mods")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="Scan a mod directory")
    p_scan.add_argument("path")
    p_scan.add_argument("--json", action="store_true", help="JSON output")
    p_scan.add_argument("--format", choices=["human", "sarif"], default="human", help="Output format (SARIF 2.1.0 for GitHub Code Scanning)")
    p_scan.add_argument("--fail-on", default="HIGH", choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"])
    p_scan.set_defaults(fn=cmd_scan)

    p_badge = sub.add_parser("badge", help="Generate a status badge SVG from a scan report")
    p_badge.add_argument("--input", required=True, help="modvet scan --json report file")
    p_badge.add_argument("--out", help="output .svg path (default: badge.svg)")
    p_badge.set_defaults(fn=cmd_badge)

    p_snap = sub.add_parser("snapshot", help="Baseline a clean mod install")
    p_snap.add_argument("path")
    p_snap.add_argument("--out", help="snapshot file (default: .modvet-snapshot.json)")
    p_snap.set_defaults(fn=cmd_snapshot)

    p_diff = sub.add_parser("diff", help="Diff installed mod against snapshot")
    p_diff.add_argument("path")
    p_diff.add_argument("--against", required=True, help="snapshot file")
    p_diff.add_argument("--fail-on", default="HIGH", choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"])
    p_diff.set_defaults(fn=cmd_diff)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
