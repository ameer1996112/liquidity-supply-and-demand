from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TRADINGVIEW_MCP_CLI = ROOT / "mcp/tradingview-mcp/src/cli/index.js"


def _run_tv(args: list[str]) -> dict:
    env = os.environ.copy()
    target_id = env.get("TV_TARGET_ID")
    if target_id:
        env["TV_TARGET_ID"] = target_id

    command = ["node", str(TRADINGVIEW_MCP_CLI), *args]
    proc = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "TradingView MCP command failed: "
            f"{' '.join(command)}\n"
            f"stderr:\n{proc.stderr}\n"
            f"stdout:\n{proc.stdout}"
        )
    return json.loads(proc.stdout)


def capture_chart_evidence(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    boxes = _run_tv(["data", "boxes"])
    labels = _run_tv(["data", "labels"])
    screenshot = _run_tv(["screenshot", "--region", "chart"])
    payload = {
        "boxes": boxes,
        "labels": labels,
        "screenshot": screenshot,
    }
    (output_dir / "raw_mcp.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload
