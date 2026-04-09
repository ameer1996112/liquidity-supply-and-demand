"""
src/pipeline/__init__.py

Exposes the primary entrypoint for the trade processing pipeline.
All heavy logic lives in the sibling modules; this file is a thin
public surface.
"""
from src.pipeline.trade_processor import process_trade  # noqa: F401
