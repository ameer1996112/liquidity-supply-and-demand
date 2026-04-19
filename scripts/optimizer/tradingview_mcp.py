from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TV_CLI_PATH = PROJECT_ROOT / "mcp" / "tradingview-mcp" / "src" / "cli" / "index.js"


class TradingViewMcpClient:
    def __init__(self, cli_path: Path | None = None) -> None:
        self._cli_path = cli_path or DEFAULT_TV_CLI_PATH

    async def run(self, *args: str) -> dict[str, Any]:
        if not self._cli_path.exists():
            raise RuntimeError(f"TradingView MCP CLI not found at {self._cli_path}")
        process = await asyncio.create_subprocess_exec(
            "node",
            str(self._cli_path),
            *args,
            cwd=str(PROJECT_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        raw = (stdout or b"").decode().strip() or (stderr or b"").decode().strip()
        if process.returncode != 0:
            raise RuntimeError(raw or f"tv {' '.join(args)} failed with exit {process.returncode}")
        if not raw:
            return {"success": True}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"tv {' '.join(args)} returned non-JSON output: {raw}") from exc

    async def healthcheck(self) -> tuple[bool, str]:
        try:
            result = await self.run("status")
        except Exception as exc:
            return False, str(exc)
        if not result.get("success"):
            return False, str(result.get("error") or "unknown MCP error")
        return True, "ok"
