"""Translation cache management using file-based storage."""

import hashlib
from pathlib import Path


def get_paragraph_hash(text: str) -> str:
    """Generate short hash for paragraph identification."""
    return hashlib.md5(text.encode()).hexdigest()[:12]


def get_cache_dir(output_dir: Path) -> Path:
    """Get translation cache directory."""
    cache_dir = output_dir / ".translations"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def get_cached_translation(output_dir: Path, text_hash: str) -> str | None:
    """Load cached translation if exists."""
    cache_file = get_cache_dir(output_dir) / f"{text_hash}.txt"
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    return None


def save_cached_translation(output_dir: Path, text_hash: str, translation: str) -> None:
    """Save translation to cache (atomic per paragraph)."""
    cache_file = get_cache_dir(output_dir) / f"{text_hash}.txt"
    cache_file.write_text(translation, encoding="utf-8")
