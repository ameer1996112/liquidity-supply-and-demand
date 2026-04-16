from __future__ import annotations

import importlib
import sys


def test_pipeline_account_guards_import_does_not_require_missing_trade_processor():
    sys.modules.pop("src.pipeline", None)
    sys.modules.pop("src.pipeline.account_guards", None)

    module = importlib.import_module("src.pipeline.account_guards")

    assert hasattr(module, "run_account_guards")
