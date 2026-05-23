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

from papercli.cache import (
    get_cached_translation,
    get_paragraph_hash,
    save_cached_translation,
)

if TYPE_CHECKING:
    from papercli.translate.config import TranslateConfig


@dataclass
class TranslationTask:
    """A paragraph to be translated."""

    task_id: int
    index: int
    clean_text: str
    refs_map: dict[str, str] = field(default_factory=dict)


def get_config() -> "TranslateConfig | None":
    from papercli.translate.config import TranslateConfig

    return TranslateConfig._instance


def translate(text: str, target_lang: str | None = None, max_retries: int = 3) -> tuple[str, bool]:
    """Translate text using OpenAI-compatible API with retry.

    Returns (translation, is_valid) where is_valid indicates placeholders are preserved.
    """
    if not text.strip():
        return "", True

    cfg = get_config()

    if target_lang is None:
        target_lang = cfg.target_lang if cfg else "Chinese"

    if cfg and cfg.debug_mode:
        clean = re.sub(r"\\[a-zA-Z]+(\{[^}]*\}|\[[^\]]*\])*", "", text)
        clean = re.sub(r"[{}\[\]$%&#_^~\\]", "", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        words = clean.split()[:15]
        truncated = " ".join(words)
        return f"（测试翻译）{truncated}……", True

    model_name = cfg.model if cfg else "gpt-4.1-nano"

    api_key = os.environ.get("MY_API_KEY")
    if not api_key:
        raise ValueError("MY_API_KEY environment variable is required")
    MY_API_URL = os.environ.get("MY_API_URL", "https://api.openai.com/v1/chat/completions")

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    input_placeholders = set(re.findall(r"\[[A-Z]+_\d+\]", text))

    def build_messages(correction: str | None = None) -> list[dict]:
        system = (
            f"You are a professional translator specializing in academic papers. "
            f"Translate the following English text to fluent and native {target_lang}. "
            "Keep all LaTeX commands, math formulas, and citations intact. "
            "IMPORTANT: Do NOT translate or modify placeholders like [MATH_0], [REF_0], [CITE_0], [MACRO_0]. "
            "Keep them exactly as they appear — same name, same number. "
            "Only output the translation, nothing else."
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": text}]
        if correction:
            messages.append({"role": "assistant", "content": correction})
            messages.append({"role": "user", "content": correction_prompt})
        return messages

    correction_prompt = (
        "Your previous translation did not preserve all placeholders correctly. "
        "Every placeholder (e.g. [MATH_0], [CITE_1], [REF_2]) must appear in the output "
        "exactly as it appears in the source — same bracket format, same type, same number. "
        "Do not rename, merge, drop, or add any placeholder. "
        "Please retranslate with all placeholders kept verbatim."
    )

    last_result = text
    for attempt in range(max_retries):
        try:
            is_retry = attempt > 0 and last_result != text
            payload = {
                "model": model_name,
                "messages": build_messages(last_result if is_retry else None),
            }
            response = requests.post(
                MY_API_URL, headers=headers, data=json.dumps(payload), timeout=60
            )
            result = response.json()
            if "choices" in result:
                translation = result["choices"][0]["message"]["content"]
                output_placeholders = set(re.findall(r"\[[A-Z]+_\d+\]", translation))
                if input_placeholders == output_placeholders:
                    return translation, True
                last_result = translation
                if attempt < max_retries - 1:
                    continue
                return last_result, False
            elif "error" in result:
                print(f"API error: {result['error']}")
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
                    continue
            return text, False
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
                continue
            return text, False
    return last_result, False


def _check_placeholders(clean_text: str, translation: str) -> bool:
    """Return True if translation preserves exactly the same placeholders as source."""
    expected = set(re.findall(r"\[[A-Z]+_\d+\]", clean_text))
    actual = set(re.findall(r"\[[A-Z]+_\d+\]", translation))
    return expected == actual


def _run_translation_batch(
    pending: list[tuple[TranslationTask, str]],
    results: dict[int, str],
    output_dir: Path | None,
    max_workers: int,
    desc: str = "Translating",
) -> list[tuple[TranslationTask, str]]:
    """Translate a batch concurrently. Returns list of (task, hash) that failed validation."""
    failed: list[tuple[TranslationTask, str]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(translate, t.clean_text): (t, h) for t, h in pending
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc=desc):
            task, h = futures[future]
            try:
                translation, is_valid = future.result()
                results[task.task_id] = translation
                if is_valid:
                    if output_dir and translation:
                        save_cached_translation(output_dir, h, translation)
                else:
                    failed.append((task, h))
            except Exception as e:
                print(f"  Translation failed: {e}")
                results[task.task_id] = ""
    return failed


def batch_translate(
    tasks: list[TranslationTask],
    output_dir: Path | None = None,
    max_workers: int = 10,
) -> dict[int, str]:
    """Translate multiple paragraphs concurrently with caching support.

    Returns dict mapping task_id -> translated text.
    Invalid cached translations (placeholder mismatch) are re-translated.
    After all work, prompts the user to retry or quit if any tasks still fail.
    """
    if not tasks:
        return {}

    cfg = get_config()
    results: dict[int, str] = {}
    pending_tasks: list[tuple[TranslationTask, str]] = []

    if output_dir:
        cache_invalid = 0
        for task in tasks:
            h = get_paragraph_hash(task.clean_text)
            cached = get_cached_translation(output_dir, h)
            if cached is not None:
                if _check_placeholders(task.clean_text, cached):
                    results[task.task_id] = cached
                else:
                    cache_invalid += 1
                    pending_tasks.append((task, h))
            else:
                pending_tasks.append((task, h))

        if results or cache_invalid:
            print(
                f"  Cached: {len(results)}, Pending: {len(pending_tasks)}"
                + (f" (re-translating {cache_invalid} invalid cache entries)" if cache_invalid else "")
            )
    else:
        pending_tasks = [(t, get_paragraph_hash(t.clean_text)) for t in tasks]

    if not pending_tasks:
        return results

    if cfg and cfg.debug_mode:
        for task, h in tqdm(pending_tasks, desc="Translating (debug)"):
            translation, is_valid = translate(task.clean_text)
            results[task.task_id] = translation
            if output_dir and translation and is_valid:
                save_cached_translation(output_dir, h, translation)
        return results

    failed = _run_translation_batch(pending_tasks, results, output_dir, max_workers)

    while failed:
        print(f"\n\033[1;31m[Warning] {len(failed)} translation(s) still have placeholder mismatches after retries:\033[0m")
        for task, _ in failed:
            expected = set(re.findall(r"\[[A-Z]+_\d+\]", task.clean_text))
            actual = set(re.findall(r"\[[A-Z]+_\d+\]", results.get(task.task_id, "")))
            missing = expected - actual
            extra = actual - expected
            preview = task.clean_text[:100].replace("\n", " ")
            parts = []
            if missing:
                parts.append(f"missing={missing}")
            if extra:
                parts.append(f"extra={extra}")
            print(f"  Task {task.task_id} ({', '.join(parts)}): {preview}…")

        try:
            choice = input("\n[r] Retry failed translations  [q] Quit: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(1)

        if choice == "q":
            raise SystemExit(1)
        elif choice == "r":
            failed = _run_translation_batch(failed, results, output_dir, max_workers, desc="Retrying")
        # any other input: re-prompt

    return results
