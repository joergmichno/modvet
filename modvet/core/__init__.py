"""Core engine (ported ClawGuard scanner: deterministic patterns, offline, no LLM)."""

from .engine import (
    Finding,
    ScanReport,
    Severity,
    scan_text,
    format_human,
    format_json,
)

__all__ = [
    "Finding",
    "ScanReport",
    "Severity",
    "scan_text",
    "format_human",
    "format_json",
]
