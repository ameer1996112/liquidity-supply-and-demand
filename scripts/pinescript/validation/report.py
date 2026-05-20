from __future__ import annotations

from pathlib import Path

from scripts.pinescript.validation.models import ValidationResult, Zone


def _zone_line(zone: Zone) -> str:
    return f"- `{zone.label}` {zone.side} {zone.bottom:g} - {zone.top:g} from `{zone.source}`"


def write_report(output_dir: Path, result: ValidationResult) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "report.md"
    lines = [
        "# TradingView Validation Report",
        "",
        f"**Scenario:** {result.scenario.name}",
        f"**Symbol:** {result.scenario.symbol}",
        f"**Timeframe:** {result.scenario.timeframe}",
        f"**Status:** {'PASS' if result.passed else 'FAIL'}",
        f"**Screenshot:** {result.screenshot_path or 'not captured'}",
        "",
        "## Expected Zones",
        "",
        *[_zone_line(zone) for zone in result.expected_zones],
        "",
        "## Actual Zones",
        "",
        *[_zone_line(zone) for zone in result.actual_zones],
        "",
        "## Mismatches",
        "",
    ]
    if result.mismatches:
        for mismatch in result.mismatches:
            lines.append(f"- `{mismatch.kind}`: {mismatch.message}")
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
