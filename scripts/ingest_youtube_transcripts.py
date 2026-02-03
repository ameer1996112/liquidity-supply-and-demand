"""
Ingest offline YouTube transcripts into Supabase RAG via RagEngine.

This script is an alternative to `harvest_youtube.py` for cases where you
have already exported transcripts (e.g. with a browser extension) and
downloaded them as a ZIP file.

Usage (from project root):
    python scripts/ingest_youtube_transcripts.py

Configuration:
    - Set the path to your transcripts ZIP via either:
        * Edit TRANSCRIPTS_ZIP_PATH below, or
        * Set env var YOUTUBE_TRANSCRIPTS_ZIP=/full/path/to/transcripts.zip

    - The ZIP is expected to contain one text-like file per video
      (.txt / .srt / .vtt). The script will:
        * Extract the video ID from the filename (first 11-char YouTube ID)
        * Use the filename as the title (minus extension)
        * Clean the text a bit (strip timestamps / line numbers where possible)
        * Refine content with an LLM into actionable trading rules
        * Ingest into Supabase using RagEngine (pgvector)
"""

from __future__ import annotations

import logging
import os
import random
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI

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
logger = logging.getLogger("YOUTUBE_OFFLINE_INGEST")


# Source of transcripts: point this to your downloaded ZIP of transcripts.
# You can also set YOUTUBE_TRANSCRIPTS_ZIP in your environment instead.
TRANSCRIPTS_ZIP_PATH = os.getenv(
    "YOUTUBE_TRANSCRIPTS_ZIP",
    "/Users/ameeramer/Downloads/transcripts.zip",  # edit this if needed
)

load_dotenv()


@dataclass
class TranscriptDoc:
    video_id: str
    title: str
    text: str

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


def _guess_video_id(name: str) -> Optional[str]:
    """Extract first 11-char YouTube video ID from a filename."""
    m = re.search(r"[A-Za-z0-9_-]{11}", name)
    return m.group(0) if m else None


def _clean_transcript(raw: str) -> str:
    """
    Light cleanup for .srt / .vtt / .txt transcripts:
    - drop pure numeric lines (indexes)
    - drop lines with timestamp arrows (-->) commonly in SRT
    """
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.isdigit():
            continue
        if "-->" in stripped:
            continue
        lines.append(stripped)
    return " ".join(lines)


def load_transcripts_from_zip(path: str) -> List[TranscriptDoc]:
    zip_path = Path(path)
    if not zip_path.exists():
        logger.error("Transcripts ZIP not found at %s", zip_path)
        return []

    docs: List[TranscriptDoc] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = [m for m in zf.infolist() if not m.is_dir()]
        for m in members:
            name = m.filename
            if not name.lower().endswith((".txt", ".srt", ".vtt")):
                continue
            try:
                data = zf.read(m)
                text = data.decode("utf-8", errors="ignore")
            except Exception as e:
                logger.warning("Failed to read %s: %s", name, e)
                continue

            video_id = _guess_video_id(name)
            if not video_id:
                logger.warning("Could not infer video ID from filename: %s", name)
                continue

            base_title = Path(name).stem
            cleaned = _clean_transcript(text)
            if not cleaned.strip():
                logger.warning("Transcript empty after cleaning for %s", name)
                continue

            docs.append(TranscriptDoc(video_id=video_id, title=base_title, text=cleaned))

    logger.info("Discovered %d transcript files in ZIP.", len(docs))
    return docs


def refine_transcript(raw_text: str, client: OpenAI) -> Optional[str]:
    """Use LLM to extract only actionable rules from a transcript."""
    if not raw_text or not raw_text.strip():
        return None

    snippet = raw_text[:16000]  # guard against extremely long docs

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
    if not TRANSCRIPTS_ZIP_PATH:
        logger.error(
            "TRANSCRIPTS_ZIP_PATH is not set. "
            "Set YOUTUBE_TRANSCRIPTS_ZIP env var or edit the constant in this script."
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

    docs = load_transcripts_from_zip(TRANSCRIPTS_ZIP_PATH)
    total = len(docs)
    if total == 0:
        logger.warning("No usable transcripts found; nothing to ingest.")
        return

    logger.info("Starting offline transcript ingest for %d documents.", total)

    for idx, doc in enumerate(docs, start=1):
        logger.info("[Transcript %d/%d] Refining: %s", idx, total, doc.title)

        refined = refine_transcript(doc.text, client)
        if not refined:
            logger.warning("Refinement produced empty output for %s", doc.url)
            time.sleep(random.uniform(1.0, 2.0))
            continue

        try:
            rag.ingest_rule(
                refined,
                metadata={
                    "source": doc.url,
                    "title": doc.title,
                    "channel_id": doc.video_id,  # video_id stored; channel may be absent
                    "kind": "youtube_transcript_offline",
                },
            )
            logger.info("[Transcript %d/%d] Ingested: %s", idx, total, doc.title)
        except Exception as e:
            logger.error("Failed to ingest rule for %s: %s", doc.url, e)

        # Safety delay between LLM calls
        time.sleep(random.uniform(1.0, 2.5))

    logger.info("Offline YouTube transcript ingest complete.")


if __name__ == "__main__":
    main()

