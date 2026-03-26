"""
Sprint 3.2: Unified AI client factory.

AIClient ABC with structured output validation. Providers are thin adapters
with no business logic. Factory selects provider from AI_PROVIDER env.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Type, TypeVar, Union, Dict, List
import base64
import io

from pydantic import BaseModel, ValidationError

from config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

REPAIR_INSTRUCTION = (
    "Your previous response was invalid JSON or did not match the required schema. "
    "Please respond again with a valid JSON object that strictly matches this schema. "
    "Include only the required fields with correct types."
)



def encode_image_for_anthropic(image_path: str, max_size_mb: float = 4.5, max_dim: int = 2000) -> dict:
    """Read an image, resize if necessary (using Pillow), and return Anthropic vision content block."""
    try:
        from PIL import Image
    except ImportError:
        raise AIClientError("Pillow is required for image processing. Run: pip install Pillow")
        
    with Image.open(image_path) as img:
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
            
        if img.width > max_dim or img.height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            
        quality = 95
        while True:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)
            size_mb = len(buf.getvalue()) / (1024 * 1024)
            if size_mb <= max_size_mb or quality <= 20:
                break
            quality -= 10
            
        b64_data = base64.b64encode(buf.getvalue()).decode("utf-8")
        
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": b64_data
        }
    }


class AIClientError(Exception):
    """Raised when AI client fails after retries."""

    pass


class AIClient(ABC):
    """
    Abstract base for AI providers. No business logic — pure transport + validation.
    """

    @abstractmethod
    def _raw_complete(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        *,
        system_prompt: str = "You are a helpful assistant. Respond with valid JSON only.",
        temperature: float = 0.1,
        max_tokens: int = 256,
        timeout: float = 30.0,
        schema: Optional[Type[T]] = None,
    ) -> str:
        """Return raw response text from the provider. Must be JSON-parseable."""
        ...

    def complete(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        schema: Type[T],
        *,
        temperature: float = 0.1,
        max_tokens: int = 256,
        timeout: float = 30.0,
        system_prompt: Optional[str] = None,
    ) -> Optional[T]:
        """
        Complete a prompt and validate response against Pydantic schema.
        Retries once with repair instruction on validation failure, then fails safely.
        """
        sys = system_prompt or "You are a helpful assistant. Respond with valid JSON only."
        raw = self._raw_complete(
            prompt,
            system_prompt=sys,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            schema=schema,
        )
        result, err = _parse_and_validate(raw, schema)
        if result is not None:
            return result
        # Retry with repair instruction
        logger.warning("AI response validation failed (%s), retrying with repair instruction", err)
        schema_hint = json.dumps(schema.model_json_schema(), indent=0)[:500]
        repair_prompt = f"{prompt}\n\n{REPAIR_INSTRUCTION}\n\nSchema (JSON): {schema_hint}"
        raw2 = self._raw_complete(
            repair_prompt,
            system_prompt=sys,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            schema=schema,
        )
        result2, _ = _parse_and_validate(raw2, schema)
        if result2 is not None:
            return result2
        logger.error("AI response still invalid after repair retry — failing safely")
        return None


def _parse_and_validate(raw: str, schema: Type[T]) -> tuple[Optional[T], Optional[str]]:
    """Parse JSON and validate against schema. Returns (instance, error_msg)."""
    if not raw or not raw.strip():
        return None, "empty response"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, f"invalid json: {e}"
    if not isinstance(data, dict):
        return None, "response is not a JSON object"
    try:
        return schema.model_validate(data), None
    except ValidationError as e:
        return None, str(e.errors())[:200]


# ── Anthropic (Claude) ───────────────────────────────────────────────────────


class AnthropicClient(AIClient):
    """Anthropic Claude provider. No business logic."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        self._api_key = api_key
        self._model = model

    def _raw_complete(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        *,
        system_prompt: str = "You are a helpful assistant. Respond with valid JSON only.",
        temperature: float = 0.1,
        max_tokens: int = 256,
        timeout: float = 30.0,
        schema: Optional[Type[T]] = None,
    ) -> str:
        try:
            from anthropic import Anthropic
        except ImportError:
            raise AIClientError("anthropic package not installed. Run: pip install anthropic")

        client = Anthropic(api_key=self._api_key or "")
        resp = client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        if not resp.content or not resp.content[0].text:
            return "{}"
        return resp.content[0].text


# ── OpenAI (stub) ───────────────────────────────────────────────────────────


class OpenAIClient(AIClient):
    """OpenAI / OpenAI-compatible API. Stub implementation."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "gpt-4o-mini",
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model

    def _raw_complete(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        *,
        system_prompt: str = "You are a helpful assistant. Respond with valid JSON only.",
        temperature: float = 0.1,
        max_tokens: int = 256,
        timeout: float = 30.0,
        schema: Optional[Type[T]] = None,
    ) -> str:
        try:
            from openai import OpenAI
        except ImportError:
            raise AIClientError("openai package not installed. Run: pip install openai")

        kwargs: dict[str, Any] = {}
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._base_url:
            kwargs["base_url"] = self._base_url
        client = OpenAI(**kwargs)
        resp = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip() or "{}"


# ── Gemini (stub) ─────────────────────────────────────────────────────────────


class GeminiClient(AIClient):
    """Google Gemini. Stub — raises NotImplementedError."""

    def _raw_complete(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        *,
        system_prompt: str = "You are a helpful assistant. Respond with valid JSON only.",
        temperature: float = 0.1,
        max_tokens: int = 256,
        timeout: float = 30.0,
        schema: Optional[Type[T]] = None,
    ) -> str:
        raise NotImplementedError("GeminiClient is a stub. Implement when needed.")


# ── Local (stub) ────────────────────────────────────────────────────────────


class LocalClient(AIClient):
    """Local / Ollama / self-hosted. Stub — raises NotImplementedError."""

    def _raw_complete(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        *,
        system_prompt: str = "You are a helpful assistant. Respond with valid JSON only.",
        temperature: float = 0.1,
        max_tokens: int = 256,
        timeout: float = 30.0,
        schema: Optional[Type[T]] = None,
    ) -> str:
        raise NotImplementedError("LocalClient is a stub. Implement when needed.")


# ── Factory ─────────────────────────────────────────────────────────────────

_CLIENT_CACHE: Optional[AIClient] = None


def get_ai_client() -> Optional[AIClient]:
    """Return the configured AI client based on AI_PROVIDER. Cached singleton."""
    global _CLIENT_CACHE
    if _CLIENT_CACHE is not None:
        return _CLIENT_CACHE
    try:
        s = get_settings()
        provider = (s.ai_provider or "anthropic").lower()
        api_key = s.ai_api_key.get_secret_value() if s.ai_api_key else None
        base_url = (s.ai_base_url or "").strip() or None
        model = s.ai_model or "claude-3-5-sonnet-20241022"

        if provider == "anthropic":
            _CLIENT_CACHE = AnthropicClient(api_key=api_key, model=model)
        elif provider == "openai":
            _CLIENT_CACHE = OpenAIClient(api_key=api_key, base_url=base_url, model=model)
        elif provider == "gemini":
            _CLIENT_CACHE = GeminiClient()
        elif provider == "local":
            _CLIENT_CACHE = LocalClient()
        else:
            logger.warning("Unknown AI_PROVIDER=%s, defaulting to anthropic", provider)
            _CLIENT_CACHE = AnthropicClient(api_key=api_key, model=model)
        logger.info("AIClient initialized: provider=%s", provider)
        return _CLIENT_CACHE
    except Exception as e:
        logger.error("AIClient init failed: %s", e)
        return None


def reset_ai_client() -> None:
    """Clear cached client (for tests)."""
    global _CLIENT_CACHE
    _CLIENT_CACHE = None


__all__ = [
    "AIClient",
    "AIClientError",
    "AnthropicClient",
    "OpenAIClient",
    "GeminiClient",
    "LocalClient",
    "get_ai_client",
    "reset_ai_client",
    "encode_image_for_anthropic",
]
