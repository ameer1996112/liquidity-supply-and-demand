"""
Ingest all local transcript files in a folder into Supabase RAG via RagEngine.

This is similar to `ingest_youtube_transcripts.py` but works on a directory
of already-extracted `.txt` / `.srt` / `.vtt` files (no ZIP and no need for
YouTube IDs). Each file is treated as one document.

Usage (from project root):
    export TRANSCRIPTS_DIR="/full/path/to/your/transcript/folder"
    python scripts/ingest_transcript_folder.py

By default, TRANSCRIPTS_DIR points at `~/Downloads/transcripts`.
"""

from __future__ import annotations

import logging
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

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
logger = logging.getLogger("TRANSCRIPT_FOLDER_INGEST")


# Root folder containing your transcript files
TRANSCRIPTS_DIR = Path(os.getenv("TRANSCRIPTS_DIR", str(Path.home() / "Downloads" / "transcripts")))

load_dotenv()


@dataclass
class TranscriptFile:
    path: Path
    title: str
    text: str

    @property
    def source(self) -> str:
        return f"file://{self.path}"


def _clean_transcript(raw: str) -> str:
    """Light cleanup for text/SRT-style transcripts."""
    lines: List[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.isdigit():
            continue
        if "-->" in s:
            continue
        lines.append(s)
    return " ".join(lines)


def load_transcripts_from_folder(root: Path) -> List[TranscriptFile]:
    if not root.exists() or not root.is_dir():
        logger.error("TRANSCRIPTS_DIR does not exist or is not a directory: %s", root)
        return []

    files: List[TranscriptFile] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if not p.suffix.lower() in {".txt", ".srt", ".vtt"}:
            continue
        try:
            raw = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning("Failed to read %s: %s", p, e)
            continue
        cleaned = _clean_transcript(raw)
        if not cleaned.strip():
            logger.warning("Transcript empty after cleaning: %s", p)
            continue
        title = p.stem
        files.append(TranscriptFile(path=p, title=title, text=cleaned))

    logger.info("Discovered %d transcript files under %s.", len(files), root)
    return files


def refine_transcript(raw_text: str, client: OpenAI) -> str | None:
    """Use LLM to extract only actionable trading rules from a transcript."""
    if not raw_text or not raw_text.strip():
        return None

    snippet = raw_text[:16000]
    system_prompt = (
        "You are a Technical Analyst. Extract ONLY actionable trading rules, "
        "entry triggers, and risk parameters from this transcript. Ignore "
        "intro/outro/fluff. Format as a bulleted list."
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
        return content.strip() if content else None
    except Exception as e:
        logger.error("Refinement LLM call failed: %s", e)
        return None


def main() -> None:
    settings = get_settings()
    if not settings.supabase_url or not (settings.supabase_service_role_key or settings.supabase_key):
        logger.error("Supabase URL/keys missing in .env; cannot initialize RagEngine.")
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

    docs = load_transcripts_from_folder(TRANSCRIPTS_DIR)
    if not docs:
        return

    total = len(docs)
    logger.info("Starting transcript folder ingest for %d documents.", total)

    for idx, doc in enumerate(docs, start=1):
        logger.info("[Transcript %d/%d] Refining: %s", idx, total, doc.title)
        refined = refine_transcript(doc.text, client)
        if not refined:
            logger.warning("Refinement produced empty output for %s", doc.source)
            time.sleep(random.uniform(1.0, 2.5))
            continue

        try:
            rag.ingest_rule(
                refined,
                metadata={
                    "source": doc.source,
                    "title": doc.title,
                    "kind": "local_transcript",
                },
            )
            logger.info("[Transcript %d/%d] Ingested: %s", idx, total, doc.title)
        except Exception as e:
            logger.error("Failed to ingest rule for %s: %s", doc.source, e)

        time.sleep(random.uniform(1.0, 2.5))

    logger.info("Transcript folder ingest complete.")


if __name__ == "__main__":
    main()

