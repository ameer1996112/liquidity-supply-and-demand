from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TV_CLI_PATH = PROJECT_ROOT / "mcp" / "tradingview-mcp" / "src" / "cli" / "index.js"
log = logging.getLogger(__name__)


class TradingViewMcpClient:
    def __init__(self, cli_path: Path | None = None, extra_env: dict[str, str] | None = None) -> None:
        self._cli_path = cli_path or DEFAULT_TV_CLI_PATH
        self._extra_env = dict(extra_env or {})

    def with_target(self, tab_id: str) -> "TradingViewMcpClient":
        env = dict(self._extra_env)
        env["TV_TARGET_ID"] = tab_id
        return TradingViewMcpClient(cli_path=self._cli_path, extra_env=env)

    def with_worker(self, worker_id: int | str | None) -> "TradingViewMcpClient":
        if worker_id is None:
            return self
        env = dict(self._extra_env)
        env["OPTIMIZER_WORKER_ID"] = str(worker_id)
        return TradingViewMcpClient(cli_path=self._cli_path, extra_env=env)

    async def run(self, *args: str) -> dict[str, Any]:
        if not self._cli_path.exists():
            raise RuntimeError(f"TradingView MCP CLI not found at {self._cli_path}")
        worker_id = self._extra_env.get("OPTIMIZER_WORKER_ID", "?")
        tab_id = self._extra_env.get("TV_TARGET_ID", "default")
        command = " ".join(args[:2] if args[:1] == ("ui",) else args[:1])
        message = "[worker-%s | tab=%s | command=%s]"
        if command == "ui eval" and os.environ.get("OPTIMIZER_VERBOSE_MCP") != "1":
            log.debug(message, worker_id, tab_id, command)
        else:
            log.info(message, worker_id, tab_id, command)
        env = os.environ.copy()
        env.update(self._extra_env)
        process = await asyncio.create_subprocess_exec(
            "node",
            str(self._cli_path),
            *args,
            cwd=str(PROJECT_ROOT),
            env=env,
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
