"""
Harvest trading strategy knowledge from YouTube and ingest into Supabase RAG.

Usage (from project root):
    python scripts/harvest_youtube.py

Requirements:
    - OPENAI_API_KEY set in environment
    - SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY configured (.env) for RagEngine
    - `scripts/setup_vector_db.py` SQL has been applied (documents + match_documents)
"""

from __future__ import annotations

import logging
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    CouldNotRetrieveTranscript,
)
import scrapetube

# Ensure project root (with `config/` and `src/`) is on sys.path when run directly
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import get_settings  # type: ignore
from src.ai.rag_engine import RagEngine  # type: ignore


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("YOUTUBE_HARVESTER")


# User: Paste your 3 Channel IDs here (e.g., "UCxxxxxxxxxxxxxxxxx")
TARGET_CHANNEL_IDS: List[str] = [
    "UC54xbL96tU58iez3YbTVTAg",
    # "UCyyyyyyyyyyyyyyyyy",
    # "UCzzzzzzzzzzzzzzzzz",
]


load_dotenv()  # Load OPENAI_API_KEY, Supabase creds, etc.


@dataclass
class VideoInfo:
    channel_id: str
    video_id: str
    title: str

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


def _extract_title(video: dict) -> str:
    """Best-effort extraction of title from scrapetube video dict."""
    try:
        runs = video.get("title", {}).get("runs", [])
        if runs:
            return runs[0].get("text", "Unknown Title")
    except Exception:
        pass
    return "Unknown Title"


def get_latest_videos(channel_id: str, limit: int = 15) -> List[VideoInfo]:
    """Fetch latest N videos from a channel via scrapetube."""
    channel_url = f"https://www.youtube.com/channel/{channel_id}"
    videos = []
    try:
        for v in scrapetube.get_channel(channel_url=channel_url):
            vid = v.get("videoId")
            if not vid:
                continue
            title = _extract_title(v)
            videos.append(VideoInfo(channel_id=channel_id, video_id=vid, title=title))
            if len(videos) >= limit:
                break
    except Exception as e:
        logger.error("Failed to fetch videos for channel %s: %s", channel_id, e)
    return videos


def get_transcript_text(video_id: str) -> Optional[str]:
    """Return full transcript text for a YouTube video, or None if unavailable.

    Uses the list_transcripts / find_transcript API to be compatible with
    multiple versions of youtube-transcript-api.
    """
    try:
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcripts.find_transcript(["en"])
        except NoTranscriptFound:
            # Fallback: try auto-generated English transcript
            transcript = transcripts.find_generated_transcript(["en"])

        parts = transcript.fetch()
        return " ".join(p.get("text", "") for p in parts)
    except (TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript) as e:
        logger.warning("No transcript for %s: %s", video_id, e)
        return None
    except Exception as e:
        logger.error("Transcript fetch failed for %s: %s", video_id, e)
        return None


def refine_transcript(raw_text: str, client: OpenAI) -> Optional[str]:
    """Use LLM to extract only actionable rules from a transcript."""
    if not raw_text or not raw_text.strip():
        return None

    # Truncate extremely long transcripts to keep prompt size reasonable
    snippet = raw_text[:12000]

    system_prompt = (
        "You are a Technical Analyst. Extract ONLY actionable trading rules, "
        "entry triggers, and risk parameters from this transcript. "
        "Ignore intros, outros, personal stories, promotions, or fluff. "
        "Format the output as a concise bulleted list."
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": snippet},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        content = resp.choices[0].message.content
        if content:
            return content.strip()
        return None
    except Exception as e:
        logger.error("Refinement LLM call failed: %s", e)
        return None


def main() -> None:
    if not TARGET_CHANNEL_IDS:
        logger.error(
            "TARGET_CHANNEL_IDS is empty. "
            "Edit scripts/harvest_youtube.py and paste your channel IDs."
        )
        return

    settings = get_settings()
    if not settings.supabase_url or not (settings.supabase_service_role_key or settings.supabase_key):
        logger.error("Supabase settings missing. Check SUPABASE_URL and keys in your .env.")
        return

    try:
        rag = RagEngine.from_settings()
    except Exception as e:
        logger.error("Failed to initialize RagEngine: %s", e)
        return

    try:
        client = OpenAI()
    except Exception as e:
        logger.error("Failed to initialize OpenAI client: %s", e)
        return

    # Collect videos across all channels first to get a total count for progress logging
    all_videos: List[VideoInfo] = []
    for cid in TARGET_CHANNEL_IDS:
        vids = get_latest_videos(cid, limit=15)
        logger.info("Channel %s: fetched %d videos", cid, len(vids))
        all_videos.extend(vids)

    total = len(all_videos)
    if total == 0:
        logger.warning("No videos discovered; check channel IDs or connectivity.")
        return

    logger.info("Starting harvest for %d videos across %d channels.", total, len(TARGET_CHANNEL_IDS))

    for idx, video in enumerate(all_videos, start=1):
        logger.info("[Video %d/%d] Fetching transcript: %s", idx, total, video.title)

        transcript = get_transcript_text(video.video_id)
        if not transcript:
            time.sleep(random.uniform(3, 6))
            continue

        refined = refine_transcript(transcript, client)
        if not refined:
            logger.warning("Refinement produced empty output for %s", video.url)
            time.sleep(random.uniform(3, 6))
            continue

        try:
            rag.ingest_rule(
                refined,
                metadata={"source": video.url, "title": video.title, "channel_id": video.channel_id},
            )
            logger.info("[Video %d/%d] Processed: %s", idx, total, video.title)
        except Exception as e:
            logger.error("Failed to ingest rule for %s: %s", video.url, e)

        # Safety delay between videos to avoid IP bans
        time.sleep(random.uniform(3, 6))

    logger.info("YouTube harvest complete.")


if __name__ == "__main__":
    main()

