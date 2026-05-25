import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.pinescript.validation import mcp_capture


ROOT = Path(__file__).resolve().parents[3]
CAPTURE = ROOT / "scripts/pinescript/validation/mcp_capture.py"
CLI = ROOT / "scripts/pinescript/validation/cli.py"


class FakeRun:
    def __init__(
        self,
        *,
        stdout: str = '{"ok": true}',
        stderr: str = "",
        returncode: int = 0,
        error: BaseException | None = None,
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.error = error
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(
        self,
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((command, kwargs))
        if self.error is not None:
            raise self.error
        return subprocess.CompletedProcess(
            args=command,
            returncode=self.returncode,
            stdout=self.stdout,
            stderr=self.stderr,
        )


def _assert_runtime_error_contains(func, needles: list[str]) -> None:
    try:
        func()
    except RuntimeError as exc:
        message = str(exc)
        for needle in needles:
            assert needle in message, f"Expected {needle!r} in {message!r}"
    else:
        raise AssertionError("Expected RuntimeError")


def test_static_contract_markers() -> None:
    source = CAPTURE.read_text(encoding="utf-8")
    required = [
        "TRADINGVIEW_MCP_CLI",
        "TV_TARGET_ID",
        "capture_chart_evidence",
        "subprocess.run(",
        "timeout=",
        "TimeoutExpired",
        "JSONDecodeError",
        '"data", "boxes"',
        '"data", "labels"',
        "screenshot",
    ]
    for needle in required:
        if needle not in source:
            raise AssertionError(f"Missing MCP capture contract marker: {needle}")

    cli_source = CLI.read_text(encoding="utf-8")
    for needle in ["capture-live", "capture_chart_evidence", "--output-dir"]:
        if needle not in cli_source:
            raise AssertionError(f"Missing CLI live capture marker: {needle}")


def test_run_tv_success_parses_json_and_passes_expected_process_context() -> None:
    fake_run = FakeRun(stdout='{"status": "ok"}')
    original_run = mcp_capture.subprocess.run
    original_target_id = os.environ.get("TV_TARGET_ID")
    os.environ["TV_TARGET_ID"] = "target-123"
    try:
        mcp_capture.subprocess.run = fake_run
        payload = mcp_capture._run_tv(["data", "boxes"])
    finally:
        mcp_capture.subprocess.run = original_run
        if original_target_id is None:
            os.environ.pop("TV_TARGET_ID", None)
        else:
            os.environ["TV_TARGET_ID"] = original_target_id

    assert payload == {"status": "ok"}
    assert len(fake_run.calls) == 1
    command, kwargs = fake_run.calls[0]
    assert command == [
        "node",
        str(mcp_capture.TRADINGVIEW_MCP_CLI),
        "data",
        "boxes",
    ]
    assert kwargs["cwd"] == mcp_capture.ROOT
    assert kwargs["text"] is True
    assert kwargs["capture_output"] is True
    assert kwargs["check"] is False
    assert kwargs["timeout"] == mcp_capture.TV_COMMAND_TIMEOUT_SECONDS
    assert kwargs["env"]["TV_TARGET_ID"] == "target-123"


def test_run_tv_nonzero_exit_raises_contextual_runtime_error() -> None:
    fake_run = FakeRun(stdout="partial output", stderr="mcp failed", returncode=2)
    original_run = mcp_capture.subprocess.run
    try:
        mcp_capture.subprocess.run = fake_run
        _assert_runtime_error_contains(
            lambda: mcp_capture._run_tv(["data", "labels"]),
            [
                "TradingView MCP command failed",
                "node",
                "data labels",
                "stderr:\nmcp failed",
                "stdout:\npartial output",
            ],
        )
    finally:
        mcp_capture.subprocess.run = original_run


def test_run_tv_invalid_json_raises_contextual_runtime_error() -> None:
    fake_run = FakeRun(stdout="{not-json", stderr="json warning")
    original_run = mcp_capture.subprocess.run
    try:
        mcp_capture.subprocess.run = fake_run
        _assert_runtime_error_contains(
            lambda: mcp_capture._run_tv(["screenshot", "--region", "chart"]),
            [
                "TradingView MCP command returned invalid JSON",
                "screenshot --region chart",
                "stderr:\njson warning",
                "stdout:\n{not-json",
            ],
        )
    finally:
        mcp_capture.subprocess.run = original_run


def test_run_tv_timeout_raises_contextual_runtime_error() -> None:
    timeout = subprocess.TimeoutExpired(
        cmd=["node", "cli.js", "data", "boxes"],
        timeout=mcp_capture.TV_COMMAND_TIMEOUT_SECONDS,
        output="partial stdout",
        stderr="partial stderr",
    )
    fake_run = FakeRun(error=timeout)
    original_run = mcp_capture.subprocess.run
    try:
        mcp_capture.subprocess.run = fake_run
        _assert_runtime_error_contains(
            lambda: mcp_capture._run_tv(["data", "boxes"]),
            [
                "TradingView MCP command timed out",
                str(mcp_capture.TV_COMMAND_TIMEOUT_SECONDS),
                "data boxes",
                "stderr:\npartial stderr",
                "stdout:\npartial stdout",
            ],
        )
    finally:
        mcp_capture.subprocess.run = original_run


def test_capture_chart_evidence_writes_raw_mcp_payload() -> None:
    calls: list[list[str]] = []

    def fake_run_tv(args: list[str]) -> dict:
        calls.append(args)
        return {"command": args}

    original_run_tv = mcp_capture._run_tv
    try:
        mcp_capture._run_tv = fake_run_tv
        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "capture"
            payload = mcp_capture.capture_chart_evidence(output_dir)
            raw_payload = json.loads(
                (output_dir / "raw_mcp.json").read_text(encoding="utf-8")
            )
    finally:
        mcp_capture._run_tv = original_run_tv

    assert calls == [
        ["data", "boxes"],
        ["data", "labels"],
        ["screenshot", "--region", "chart"],
    ]
    assert payload == {
        "boxes": {"command": ["data", "boxes"]},
        "labels": {"command": ["data", "labels"]},
        "screenshot": {"command": ["screenshot", "--region", "chart"]},
    }
    assert raw_payload == payload


def main() -> None:
    test_static_contract_markers()
    test_run_tv_success_parses_json_and_passes_expected_process_context()
    test_run_tv_nonzero_exit_raises_contextual_runtime_error()
    test_run_tv_invalid_json_raises_contextual_runtime_error()
    test_run_tv_timeout_raises_contextual_runtime_error()
    test_capture_chart_evidence_writes_raw_mcp_payload()

    print("TradingView validation MCP capture static contract passed")


if __name__ == "__main__":
    main()
