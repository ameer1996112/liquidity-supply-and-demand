#!/usr/bin/env python3
"""
Test Visual Annotator via LLM Council.
Validates the Knowledge Translation Architecture for Prop Firm trading
by passing a historical chart screenshot to Claude 3.5 Sonnet.
"""

import sys
import json
import logging
from typing import Any, Dict, List
from pathlib import Path
from pydantic import BaseModel, Field

# Ensure src is in PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

from config.logging_config import configure_logging
from src.ai.llm_client import get_ai_client, encode_image_for_anthropic

configure_logging()
logger = logging.getLogger(__name__)

class DimensionScore(BaseModel):
    score: int = Field(..., ge=1, le=10, description="Score from 1 to 10")
    reasoning: str = Field(..., description="1-2 sentences explaining the score based on visual evidence")

class VisualAnnotatorResult(BaseModel):
    zone_quality: DimensionScore = Field(..., description="Is the zone fresh, sharp, and untested?")
    liquidity_context: DimensionScore = Field(..., description="Did it sweep liquidity or induce early participants?")
    structural_alignment: DimensionScore = Field(..., description="Is it aligned with the 1H/4H market structure?")
    environment_health: DimensionScore = Field(..., description="Is the price action clean or choppy/low momentum?")
    overall_decision: str = Field(..., description="'APPROVE' or 'REJECT' based on prop firm constraints")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence level in the analysis")

SYSTEM_PROMPT = """You are the lead risk officer for a prop firm algorithmic trading desk.
Your job is to visually evaluate SMC (Smart Money Concepts) trade setups.
You have strict constraints: max 5% daily drawdown. You must reject any "C-quality" setups.
Only approve A+ setups with clear structural alignment, strong liquidity sweeps, and clean price action."""

USER_PROMPT_TEMPLATE = """Evaluate this trade signal against the 4-dimension rubric.

Webhook Payload:
{payload}

Analyze the attached 5m/1H chart screenshot.
Grade the setup out of 10 for Zone Quality, Liquidity Context, Structural Alignment, and Environment Health.
Be extremely strict. Reject if the market context is choppy or misaligned."""

def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/test_visual_annotator.py <path_to_screenshot.png> '<json_payload>'")
        sys.exit(1)

    image_path = sys.argv[1]
    payload_str = sys.argv[2]

    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON payload: %s", e)
        sys.exit(1)

    if not Path(image_path).exists():
        logger.error("Image file not found: %s", image_path)
        sys.exit(1)

    logger.info("Initializing AI Client...")
    client = get_ai_client()
    if not client:
        logger.error("Failed to initialize AI Client. Ensure AI_PROVIDER=anthropic and API key is set.")
        sys.exit(1)

    logger.info("Encoding image %s...", image_path)
    try:
        image_block = encode_image_for_anthropic(image_path)
    except Exception as e:
        logger.error("Image encoding failed: %s", e)
        sys.exit(1)

    prompt_text = USER_PROMPT_TEMPLATE.format(payload=json.dumps(payload, indent=2))
    
    # Multimodal list prompt
    prompt: List[Dict[str, Any]] = [
        image_block,
        {
            "type": "text",
            "text": prompt_text
        }
    ]

    logger.info("Sending to Claude 3.5 Sonnet for visual annotation...")
    try:
        result = client.complete(
            prompt=prompt,
            schema=VisualAnnotatorResult,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=1024,
            timeout=60.0
        )
        if result:
            print("\n=== VISUAL ANNOTATOR RESULT ===")
            print(result.model_dump_json(indent=2))
        else:
            logger.error("Visual Annotator returned None")
            sys.exit(1)
    except Exception as e:
        logger.error("Vision evaluation failed: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
