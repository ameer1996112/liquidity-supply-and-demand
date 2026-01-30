"""
AI Guardian - Trade Validation Layer for Liquidity Supply & Demand Strategy

This module implements an AI-powered validation layer that analyzes incoming trade signals
against the "RD Forex / Liquidity S&D" strategy rules before execution.

DOMAIN KNOWLEDGE (Liquidity Supply & Demand Rules):
=================================================

1. THE INDUCEMENT RULE:
   A valid zone MUST have "Liquidity" (a swing high/low) built up before it.
   - Price must create a pullback (inducement) before reaching the zone
   - If price rushes straight from the start without creating inducement first, the zone is FAKE
   - Inducement = liquidity that gets swept, triggering institutional orders
   - REJECT trades where liq_swept=False or no clear inducement structure

2. THE ARRIVAL RULE:
   Price must arrive at the zone "Aggressively" (big candles, straight line).
   - AGGRESSIVE arrival = Large impulse candles, minimal pullbacks, fast momentum
   - COMPRESSED arrival = Choppy, small stairs, building liquidity to smash through
   - If price "compresses" into the zone, it's likely building liquidity to break it
   - REJECT trades with compressed/choppy arrival (low departure_strength)

3. THE INVALIDATION RULE:
   If the entry candle closes INSIDE the zone or past it, the zone has failed.
   - We need a clear rejection wick or close outside the zone
   - entry_model="FLIP" or "DIR_CLOSE" = valid rejection patterns
   - entry_model="BREAK_CANDLE" with close inside = potential failure
   - REJECT trades where the zone appears mitigated

Author: AI Guardian System
Version: 1.0.0
"""

import asyncio
import json
import logging
from enum import Enum
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ══════════════════════════════════════════════════════════


class ArrivalType(str, Enum):
    """
    How price arrived at the zone.

    AGGRESSIVE: Big candles, straight line, fast momentum (GOOD)
    COMPRESSED: Choppy, small stairs, building liquidity (BAD - likely to break zone)
    UNKNOWN: Insufficient data to determine
    """
    AGGRESSIVE = "aggressive"
    COMPRESSED = "compressed"
    UNKNOWN = "unknown"


class TradeContext(BaseModel):
    """
    Input context for AI analysis.

    Contains all relevant data from the TradingView signal needed to evaluate
    whether the trade setup follows Liquidity S&D rules.
    """

    # Core trade info
    symbol: str = Field(..., description="Trading symbol (e.g., EURUSD, XAUUSD)")
    side: str = Field(..., description="Trade direction: 'buy' or 'sell'")
    timeframe: str = Field(default="M5", description="Chart timeframe")

    # Zone information
    zone_type: str = Field(..., description="Zone type: 'demand' or 'supply'")
    zone_id: Optional[int] = Field(default=None, description="Unique zone identifier")

    # Liquidity Sweep Status (THE INDUCEMENT RULE)
    liq_swept: bool = Field(
        ...,
        description="Whether liquidity/inducement was swept before entry. "
                    "Must be True for valid setups."
    )
    target_swept: bool = Field(
        default=False,
        description="Whether the target structure was swept"
    )
    caused_sweep: bool = Field(
        default=False,
        description="Whether this zone caused a liquidity sweep"
    )

    # Arrival Quality (THE ARRIVAL RULE)
    departure_strength: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="How aggressively price departed from the zone (0-100). "
                    "High = aggressive move, Low = compressed/choppy"
    )
    return_strength: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="How fast price returned to the zone after sweep (0-100). "
                    "High = V-reversal, Low = slow grind"
    )

    # Entry Pattern (THE INVALIDATION RULE)
    entry_model: Optional[str] = Field(
        default=None,
        description="Entry model used: 'FLIP', 'DIR_CLOSE', 'BREAK_CANDLE'"
    )

    # Quality Metrics
    score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Zone quality score from TradingView (0-100)"
    )
    freshness: Optional[int] = Field(
        default=None,
        description="Zone freshness: 1=first touch, 0=retrace"
    )
    is_accuracy: bool = Field(
        default=False,
        description="Whether this is an 'Accuracy Zone' (tighter entry)"
    )

    # Market Context
    session: Optional[int] = Field(
        default=None,
        description="Trading session: 0=Asian, 1=London, 2=NY, 3=Off-hours"
    )
    trend: Optional[int] = Field(
        default=None,
        description="Trend direction: 1=bullish, 0=bearish"
    )
    htf_trend: Optional[int] = Field(
        default=None,
        description="Higher timeframe trend: 1=bullish, 0=bearish"
    )

    # Additional features
    atr_ratio: Optional[float] = Field(default=None, description="Zone size relative to ATR")
    rsi: Optional[float] = Field(default=None, description="RSI value at entry")
    rvol: Optional[float] = Field(default=None, description="Relative volume")
    adx: Optional[float] = Field(default=None, description="ADX strength")
    touch_count: Optional[int] = Field(default=None, description="Number of zone touches")
    base_quality: Optional[float] = Field(default=None, description="Base candle quality")
    liquidity_distance: Optional[float] = Field(default=None, description="Distance to liquidity")
    liquidity_spread: Optional[float] = Field(default=None, description="Liquidity spread")

    @field_validator('side')
    @classmethod
    def validate_side(cls, v: str) -> str:
        v = v.lower()
        if v not in ('buy', 'sell'):
            raise ValueError(f"side must be 'buy' or 'sell', got '{v}'")
        return v

    @field_validator('zone_type')
    @classmethod
    def validate_zone_type(cls, v: str) -> str:
        v = v.lower()
        if v not in ('demand', 'supply'):
            raise ValueError(f"zone_type must be 'demand' or 'supply', got '{v}'")
        return v

    def get_arrival_type(self) -> ArrivalType:
        """
        Determine arrival type based on departure_strength.

        Aggressive: departure_strength >= 60
        Compressed: departure_strength < 40
        Unknown: 40-60 or no data
        """
        if self.departure_strength is None:
            return ArrivalType.UNKNOWN
        if self.departure_strength >= 60:
            return ArrivalType.AGGRESSIVE
        if self.departure_strength < 40:
            return ArrivalType.COMPRESSED
        return ArrivalType.UNKNOWN


class AIDecision(str, Enum):
    """AI's decision on whether to execute the trade."""
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class AIAnalysisResult(BaseModel):
    """
    Structured output from AI analysis.

    The AI must return exactly these fields in JSON format.
    """

    decision: AIDecision = Field(
        ...,
        description="Final decision: APPROVE or REJECT"
    )

    confidence: int = Field(
        ...,
        ge=0,
        le=100,
        description="Confidence score (0-100). Higher = more certain."
    )

    reasoning: str = Field(
        ...,
        max_length=500,
        description="Brief explanation of the decision citing specific rule violations or confirmations."
    )

    rule_checks: Dict[str, bool] = Field(
        default_factory=dict,
        description="Individual rule check results: inducement_valid, arrival_valid, invalidation_clear"
    )


class AIGuardianError(Exception):
    """Custom exception for AI Guardian errors."""
    pass


# ══════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ══════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are an AI Trade Guardian specializing in Liquidity Supply & Demand (S&D) analysis.

Your role is to validate incoming trade signals against strict S&D rules BEFORE execution.
You must analyze the provided trade context and return a structured JSON decision.

## TRADING RULES (YOU MUST ENFORCE THESE STRICTLY):

### RULE 1: THE INDUCEMENT RULE
A valid zone MUST have liquidity swept before entry.
- CHECK: `liq_swept` must be TRUE
- CHECK: `caused_sweep` should be TRUE (zone caused the sweep)
- RATIONALE: Liquidity sweeps trigger institutional orders. No sweep = retail trap.
- VIOLATION: If liq_swept=false → REJECT with "No inducement sweep detected"

### RULE 2: THE ARRIVAL RULE
Price must arrive at the zone AGGRESSIVELY (big candles, momentum).
- CHECK: `departure_strength` >= 50 indicates aggressive departure
- CHECK: `return_strength` >= 30 indicates fast return (V-shape)
- RATIONALE: Compressed/choppy arrival means price is building liquidity to BREAK the zone.
- VIOLATION: If departure_strength < 40 → REJECT with "Compressed arrival - zone likely to break"

### RULE 3: THE INVALIDATION RULE
The entry must show clear rejection, not closure inside zone.
- CHECK: `entry_model` should be "FLIP" or "DIR_CLOSE" (clear rejection patterns)
- CHECK: "BREAK_CANDLE" is acceptable only with other confirmations
- RATIONALE: Close inside zone = zone failed. We need rejection wicks.
- VIOLATION: Weak entry model with low score → REJECT with "Zone invalidation risk"

### ADDITIONAL QUALITY CHECKS:
- `freshness` == 1 (first touch) is preferred. Retrace entries (0) are riskier.
- `score` >= 60 indicates decent zone quality
- `session` 1 or 2 (London/NY) is preferred over 0 or 3 (Asian/Off-hours)
- `trend` alignment: For demand zones, trend=1 (bullish) is better. For supply, trend=0.
- `is_accuracy` zones have tighter entries and are generally higher quality.

## DECISION LOGIC:

APPROVE if:
- liq_swept=true AND
- departure_strength >= 50 (or unknown with other strong confirmations) AND
- entry_model is valid AND
- score >= 50

REJECT if ANY of these:
- liq_swept=false (CRITICAL - always reject)
- departure_strength < 40 (compressed arrival)
- score < 40 (low quality zone)
- Multiple warning signs even if no single critical failure

## OUTPUT FORMAT (STRICT JSON):

You MUST respond with ONLY a valid JSON object:
{
    "decision": "APPROVE" or "REJECT",
    "confidence": 0-100,
    "reasoning": "Brief explanation citing specific rules",
    "rule_checks": {
        "inducement_valid": true/false,
        "arrival_valid": true/false,
        "invalidation_clear": true/false
    }
}

DO NOT include any text outside the JSON. DO NOT use markdown code blocks."""


# ══════════════════════════════════════════════════════════
# AI GUARDIAN CLASS
# ══════════════════════════════════════════════════════════


class AIGuardian:
    """
    AI-powered trade validation layer.

    Validates incoming trade signals against Liquidity S&D rules
    using either OpenAI or Anthropic as the AI provider.

    Architecture:
    - Dependency Injection: Accept async client in __init__
    - Fail-Open: On timeout/error, allow trade through (safety)
    - Structured Output: Force JSON response for reliable parsing

    Usage:
        guardian = AIGuardian(provider="anthropic", api_key="sk-...")
        result = await guardian.analyze_signal(trade_context)
        if result.decision == AIDecision.REJECT:
            # Log and skip trade
        else:
            # Execute trade
    """

    def __init__(
        self,
        provider: Literal["openai", "anthropic"],
        api_key: str,
        model: Optional[str] = None,
        timeout: float = 5.0,
        base_url: Optional[str] = None,
    ):
        """
        Initialize AI Guardian.

        Args:
            provider: AI provider ("openai" or "anthropic")
            api_key: API key for the provider
            model: Model to use (None = provider default)
            timeout: Timeout in seconds for API calls
            base_url: Base URL for OpenAI-compatible APIs (e.g. Groq). Required for non-OpenAI providers.
        """
        self.provider = provider
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = base_url

        # Set default models
        if model:
            self.model = model
        elif provider == "openai":
            self.model = "gpt-4o-mini"  # Fast and cheap
        else:
            self.model = "claude-3-haiku-20240307"  # Fast and cheap

        self._client = None

        logger.info(f"AI Guardian initialized: provider={provider}, model={self.model}")

    async def _get_openai_client(self):
        """Lazy-load OpenAI async client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                from backend.config import get_settings
                settings = get_settings()
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=settings.ai_base_url,
                )
            except ImportError:
                raise AIGuardianError("openai package not installed. Run: pip install openai")
        return self._client

    async def _get_anthropic_client(self):
        """Lazy-load Anthropic async client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise AIGuardianError("anthropic package not installed. Run: pip install anthropic")
        return self._client

    def _build_user_message(self, context: TradeContext) -> str:
        """Build user message with trade context."""
        arrival_type = context.get_arrival_type()

        # Build structured context
        data = {
            "symbol": context.symbol,
            "side": context.side,
            "zone_type": context.zone_type,
            "zone_id": context.zone_id,
            "timeframe": context.timeframe,

            # Inducement Rule data
            "liq_swept": context.liq_swept,
            "target_swept": context.target_swept,
            "caused_sweep": context.caused_sweep,

            # Arrival Rule data
            "arrival_type": arrival_type.value,
            "departure_strength": context.departure_strength,
            "return_strength": context.return_strength,

            # Invalidation Rule data
            "entry_model": context.entry_model,

            # Quality metrics
            "score": context.score,
            "freshness": context.freshness,
            "is_accuracy": context.is_accuracy,

            # Market context
            "session": context.session,
            "trend": context.trend,
            "htf_trend": context.htf_trend,

            # Additional features
            "atr_ratio": context.atr_ratio,
            "rsi": context.rsi,
            "touch_count": context.touch_count,
        }

        return f"""Analyze this trade signal and return your decision as JSON:

TRADE CONTEXT:
{json.dumps(data, indent=2)}

Remember: ONLY return valid JSON, no other text."""

    async def _call_openai(self, context: TradeContext) -> str:
        """Call OpenAI API with structured output."""
        client = await self._get_openai_client()

        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": self._build_user_message(context)},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Low temperature for consistent decisions
                max_tokens=500,
            ),
            timeout=self.timeout
        )

        return response.choices[0].message.content

    async def _call_anthropic(self, context: TradeContext) -> str:
        """Call Anthropic API with structured output."""
        client = await self._get_anthropic_client()

        response = await asyncio.wait_for(
            client.messages.create(
                model=self.model,
                max_tokens=500,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": self._build_user_message(context)},
                ],
            ),
            timeout=self.timeout
        )

        # Extract text from response
        return response.content[0].text

    def _parse_response(self, raw_response: str) -> AIAnalysisResult:
        """Parse AI response into structured result."""
        try:
            # Clean up response (remove markdown if present)
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                # Extract JSON from code block
                lines = cleaned.split("\n")
                json_lines = []
                in_block = False
                for line in lines:
                    if line.startswith("```"):
                        in_block = not in_block
                        continue
                    if in_block or not line.startswith("```"):
                        json_lines.append(line)
                cleaned = "\n".join(json_lines)

            # Parse JSON
            data = json.loads(cleaned)

            # Validate and create result
            return AIAnalysisResult.model_validate(data)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Raw response: {raw_response}")
            # Return a conservative REJECT on parse failure
            return AIAnalysisResult(
                decision=AIDecision.REJECT,
                confidence=0,
                reasoning=f"AI response parse error: {str(e)[:100]}",
                rule_checks={}
            )
        except Exception as e:
            logger.error(f"Unexpected error parsing AI response: {e}")
            return AIAnalysisResult(
                decision=AIDecision.REJECT,
                confidence=0,
                reasoning=f"Unexpected parse error: {str(e)[:100]}",
                rule_checks={}
            )

    async def analyze_signal(self, context: TradeContext) -> AIAnalysisResult:
        """
        Analyze a trade signal against Liquidity S&D rules.

        This is the main entry point for trade validation.

        Args:
            context: TradeContext with all signal data

        Returns:
            AIAnalysisResult with decision, confidence, and reasoning

        Raises:
            No exceptions - on error, returns APPROVE with low confidence (fail-open)
        """
        try:
            logger.info(f"AI Guardian analyzing: {context.symbol} {context.side} zone={context.zone_id}")

            # Call appropriate provider
            if self.provider == "openai":
                raw_response = await self._call_openai(context)
            else:
                raw_response = await self._call_anthropic(context)

            # Parse response
            result = self._parse_response(raw_response)

            logger.info(
                f"AI Guardian decision: {result.decision.value} "
                f"(confidence={result.confidence}) - {result.reasoning[:100]}"
            )

            return result

        except asyncio.TimeoutError:
            logger.warning(f"AI Guardian timeout after {self.timeout}s - allowing trade (fail-open)")
            return AIAnalysisResult(
                decision=AIDecision.APPROVE,
                confidence=50,
                reasoning=f"AI timeout after {self.timeout}s - SKIP_CHECK (fail-open)",
                rule_checks={"timeout": True}
            )

        except Exception as e:
            logger.error(f"AI Guardian error: {e} - allowing trade (fail-open)")
            return AIAnalysisResult(
                decision=AIDecision.APPROVE,
                confidence=50,
                reasoning=f"AI error: {str(e)[:100]} - SKIP_CHECK (fail-open)",
                rule_checks={"error": True}
            )


# ══════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ══════════════════════════════════════════════════════════


def create_ai_guardian_from_settings() -> Optional[AIGuardian]:
    """
    Factory function to create AIGuardian from config settings.

    Returns:
        AIGuardian instance if enabled and configured, None otherwise
    """
    from backend.config import get_settings

    settings = get_settings()

    if not settings.ai_filter_enabled:
        logger.info("AI Guardian disabled via AI_FILTER_ENABLED=False")
        return None

    api_key = settings.ai_api_key.get_secret_value()
    if not api_key:
        logger.warning("AI Guardian enabled but no API key configured - disabling")
        return None

    return AIGuardian(
        provider=settings.ai_provider,
        api_key=api_key,
        model=settings.ai_model or None,
        timeout=settings.ai_timeout_seconds,
        base_url=settings.ai_base_url,
    )


def build_trade_context(data: Dict[str, Any]) -> TradeContext:
    """
    Build TradeContext from raw webhook/queue payload.

    Args:
        data: Raw trade data dictionary from TradingView webhook

    Returns:
        TradeContext ready for AI analysis
    """
    return TradeContext(
        symbol=str(data.get("symbol", "UNKNOWN")).upper(),
        side=str(data.get("side", "buy")).lower(),
        timeframe=str(data.get("timeframe", "M5")),
        zone_type=str(data.get("zone_type", "demand")).lower(),
        zone_id=data.get("zone_id"),

        # Liquidity sweep data
        liq_swept=bool(data.get("liq_swept", False)),
        target_swept=bool(data.get("target_swept", False)),
        caused_sweep=bool(data.get("caused_sweep", False)),

        # Quality metrics
        departure_strength=data.get("departure_strength"),
        return_strength=data.get("return_strength"),
        entry_model=data.get("entry_model"),
        score=data.get("score"),
        freshness=data.get("freshness"),
        is_accuracy=bool(data.get("is_accuracy", False)),

        # Market context
        session=data.get("session"),
        trend=data.get("trend"),
        htf_trend=data.get("htf_trend"),

        # Additional features
        atr_ratio=data.get("atr_ratio"),
        rsi=data.get("rsi"),
        rvol=data.get("rvol"),
        adx=data.get("adx"),
        touch_count=data.get("touch_count"),
        base_quality=data.get("base_quality"),
        liquidity_distance=data.get("liquidity_distance"),
        liquidity_spread=data.get("liquidity_spread"),
    )
