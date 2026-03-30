"""Translation API client with concurrent batch support."""

from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from tqdm import tqdm

from translator.cache import (
    get_cached_translation,
    get_paragraph_hash,
    save_cached_translation,
)

if TYPE_CHECKING:
    from translator.cli import Config


@dataclass
class TranslationTask:
    """A paragraph to be translated."""

    task_id: int  # Global unique ID for translation result mapping
    index: int  # Position in result_parts for file assembly
    clean_text: str  # Cleaned text for translation API
    refs_map: dict[str, str] = field(default_factory=dict)  # Placeholder -> original LaTeX


def get_config() -> "Config | None":
    """Get the current Config instance."""
    from translator.cli import Config

    return Config._instance


def translate(text: str, target_lang: str = "Chinese", max_retries: int = 3) -> str:
    """Translate text using bltcy.ai API with retry."""
    if not text.strip():
        return ""

    cfg = get_config()
    if cfg and cfg.debug_mode:
        # Return mock translation for testing (pure Chinese, no special chars)
        clean = re.sub(r"\\[a-zA-Z]+(\{[^}]*\}|\[[^\]]*\])*", "", text)
        clean = re.sub(r"[{}\[\]$%&#_^~\\]", "", clean)  # Remove special chars
        clean = re.sub(r"\s+", " ", clean).strip()
        words = clean.split()[:15]
        truncated = " ".join(words)
        return f"（测试翻译）{truncated}……"

    api_key = os.environ.get("ONE_API")
    if not api_key:
        raise ValueError("ONE_API environment variable is required")
    api_url = os.environ.get("API_URL", "https://api.bltcy.ai/v1/chat/completions")
    model_name = cfg.model if cfg else "gpt-5-nano"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    f"You are a professional translator specializing in academic papers. "
                    f"Translate the following English text to fluent and native {target_lang}. "
                    "Keep all LaTeX commands, math formulas, and citations intact. "
                    "IMPORTANT: Do NOT translate or modify placeholders like [MATH_0], [REF_0], [CITE_0], [MACRO_0]. "
                    "Keep them exactly as they appear. "
                    "Only output the translation, nothing else."
                ),
            },
            {"role": "user", "content": text},
        ],
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(
                api_url, headers=headers, data=json.dumps(payload), timeout=60
            )
            result = response.json()
            if "choices" in result:
                return result["choices"][0]["message"]["content"]
            elif "error" in result:
                print(f"API error: {result['error']}")
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
                    continue
            return text  # Return original on failure
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
                continue
            return text
    return text


def batch_translate(
    tasks: list[TranslationTask],
    output_dir: Path | None = None,
    max_workers: int = 10,
) -> dict[int, str]:
    """Translate multiple paragraphs concurrently with caching support.

    Returns dict mapping task_id -> translated text.
    """
    if not tasks:
        return {}

    cfg = get_config()
    results = {}
    pending_tasks = []

    # Check cache for each task (if output_dir provided)
    if output_dir:
        for task in tasks:
            h = get_paragraph_hash(task.clean_text)
            cached = get_cached_translation(output_dir, h)
            if cached is not None:
                results[task.task_id] = cached
            else:
                pending_tasks.append((task, h))

        if results:
            print(f"  Cached: {len(results)}, Pending: {len(pending_tasks)}")
    else:
        pending_tasks = [(t, get_paragraph_hash(t.clean_text)) for t in tasks]

    if not pending_tasks:
        return results

    # Debug mode: sequential mock translation
    if cfg and cfg.debug_mode:
        for task, h in tqdm(pending_tasks, desc="Translating (debug)"):
            translation = translate(task.clean_text)
            results[task.task_id] = translation
            if output_dir and translation:
                save_cached_translation(output_dir, h, translation)
        return results

    # Translate pending paragraphs concurrently
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(translate, t.clean_text): (t, h) for t, h in pending_tasks
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc="Translating"):
            task, h = futures[future]
            try:
                translation = future.result()
                results[task.task_id] = translation
                # Save immediately after each translation (atomic)
                if output_dir and translation:
                    save_cached_translation(output_dir, h, translation)
            except Exception as e:
                print(f"  Translation failed: {e}")
                results[task.task_id] = ""

    return results
