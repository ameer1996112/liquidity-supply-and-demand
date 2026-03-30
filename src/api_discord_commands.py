"""
Discord interactions endpoint for two-way command handling.

Discord sends POST requests to this endpoint when a user types a command
in a channel where the bot has been registered.

Verification: Discord requires Ed25519 signature verification on all interaction requests.
Set DISCORD_PUBLIC_KEY in environment to enable signature verification.

Registration: Register slash commands with Discord via:
    python scripts/register_discord_commands.py
"""

import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from config import get_settings


logger = logging.getLogger(__name__)

discord_commands_router = APIRouter(prefix="/api/discord", tags=["discord"])

# Discord interaction types
INTERACTION_TYPE_PING = 1
INTERACTION_TYPE_APPLICATION_COMMAND = 2

# Discord response types
RESPONSE_TYPE_PONG = 1
RESPONSE_TYPE_CHANNEL_MESSAGE = 4


def _verify_discord_signature(body: bytes, signature: str, timestamp: str) -> bool:
    """Verify that the request is genuinely from Discord using Ed25519."""
    public_key = get_settings().discord_public_key
    if not public_key:
        logger.warning("DISCORD_PUBLIC_KEY not set — skipping signature verification")
        return True

    try:
        from nacl.signing import VerifyKey

        verify_key = VerifyKey(bytes.fromhex(public_key))
        message = (timestamp + body.decode("utf-8")).encode()
        verify_key.verify(message, bytes.fromhex(signature))
        return True
    except Exception:
        logger.warning("Discord signature verification failed", exc_info=True)
        return False


@discord_commands_router.post("/interactions")
async def discord_interactions(
    request: Request,
    x_signature_ed25519: str = Header(default=""),
    x_signature_timestamp: str = Header(default=""),
):
    """
    Handle Discord interaction callbacks (slash commands).
    Discord POSTs here when a user uses /close, /pause, etc.
    """
    body = await request.body()

    # Verify signature
    if not _verify_discord_signature(body, x_signature_ed25519, x_signature_timestamp):
        raise HTTPException(status_code=401, detail="Invalid request signature")

    try:
        interaction = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Discord ping — must respond with pong
    if interaction.get("type") == INTERACTION_TYPE_PING:
        return JSONResponse({"type": RESPONSE_TYPE_PONG})

    # Slash command interaction
    if interaction.get("type") == INTERACTION_TYPE_APPLICATION_COMMAND:
        return await _handle_slash_command(request, interaction)

    return JSONResponse({"type": RESPONSE_TYPE_PONG})


async def _handle_slash_command(request: Request, interaction: dict) -> JSONResponse:
    """Route slash command to CommandRouter and return Discord response."""
    data = interaction.get("data", {})
    command_name = data.get("name", "")
    options = data.get("options", [])
    user_id = str(
        interaction.get("member", {}).get("user", {}).get("id")
        or interaction.get("user", {}).get("id", "")
    )

    # Build command text from slash command name + options
    args_text = " ".join(str(opt.get("value", "")) for opt in options)
    text = f"/{command_name} {args_text}".strip()

    # Get dependencies from app state
    supabase = getattr(request.app.state, "supabase", None)
    meta_api = getattr(request.app.state, "meta_api", None)

    if not supabase:
        logger.error("Discord interactions: supabase not available on app.state")
        return _discord_reply("Internal error: database not available.", ephemeral=True)

    from src.services.command_router import CommandRouter

    router = CommandRouter(supabase=supabase, meta_api=meta_api)

    reply_text = []

    async def capture_reply(msg: str):
        reply_text.append(msg)

    await router.handle(
        platform="discord",
        user_id=user_id,
        text=text,
        reply_fn=capture_reply,
    )

    if reply_text:
        return _discord_reply(reply_text[0], ephemeral=True)

    # Silently ignored (unauthorized user) — return empty acknowledgement
    return JSONResponse({"type": RESPONSE_TYPE_CHANNEL_MESSAGE, "data": {"flags": 64, "content": ""}})


def _discord_reply(content: str, ephemeral: bool = True) -> JSONResponse:
    """Return a Discord channel message response (ephemeral = only visible to the user)."""
    flags = 64 if ephemeral else 0  # 64 = EPHEMERAL flag
    return JSONResponse({
        "type": RESPONSE_TYPE_CHANNEL_MESSAGE,
        "data": {
            "content": content,
            "flags": flags,
        },
    })
