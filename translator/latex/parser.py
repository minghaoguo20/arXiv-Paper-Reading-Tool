"""LaTeX document parsing and translation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from translator.api import TranslationTask, batch_translate

if TYPE_CHECKING:
    from translator.cli import Config


@dataclass
class FileParseResult:
    """Result of parsing a file for translation."""

    file_path: Path = field(default_factory=lambda: Path())
    result_parts: list[str | TranslationTask] = field(default_factory=list)
    tasks: list[TranslationTask] = field(default_factory=list)
    # (index, original_lines, task) - original_lines is list[str] for multi-line captions
    caption_tasks: list[tuple[int, list[str], TranslationTask]] = field(default_factory=list)


def get_config() -> "Config | None":
    """Get the current Config instance."""
    from translator.cli import Config

    return Config._instance


def is_translatable_paragraph(text: str) -> bool:
    """Check if a text block should be translated."""
    text = text.strip()
    if len(text) < 30:
        return False
    # Skip if mostly LaTeX commands
    if text.count("\\") > len(text) / 10:
        return False
    # Skip if it's a single command
    if re.match(r"^\\[a-zA-Z]+(\{[^}]*\}|\[[^\]]*\])*$", text):
        return False
    return True


def clean_for_translation(text: str) -> str:
    """Clean LaTeX text before translation, removing commands but keeping content."""
    # Remove comments
    text = re.sub(r"%.*", "", text)
    # Remove \begin{...}[options] and \end{...}
    text = re.sub(r"\\begin\{[^}]+\}(\[[^\]]*\])?", "", text)
    text = re.sub(r"\\end\{[^}]+\}", "", text)
    # Remove \item with optional label
    text = re.sub(r"\\item(\[[^\]]*\])?", "", text)
    # Remove \label{...}
    text = re.sub(r"\\label\{[^}]*\}", "", text)
    # Simplify formatting commands but keep content
    text = re.sub(r"\\textit\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\textbf\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\emph\{([^{}]*)\}", r"\1", text)
    # Keep citations as [cite]
    text = re.sub(r"~?\\cite[pt]?\{[^}]*\}", "[cite]", text)
    text = re.sub(r"~?\\ref\{[^}]*\}", "[ref]", text)
    # Clean up whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def escape_for_latex(text: str) -> str:
    """Escape special characters in translated text for LaTeX."""
    # Remove any remaining LaTeX commands (they shouldn't be in translation)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    # Remove braces (they're LaTeX-specific)
    text = text.replace("{", "").replace("}", "")
    # Escape special LaTeX characters
    text = text.replace("\\", "")  # Remove backslashes
    text = text.replace("$", r"\$")
    text = text.replace("%", r"\%")
    text = text.replace("&", r"\&")
    text = text.replace("#", r"\#")
    text = text.replace("_", r"\_")
    text = text.replace("^", "")
    text = text.replace("~", " ")
    # Clean up multiple spaces
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_caption_content(text: str) -> str:
    """Extract content from \\caption{...} handling nested braces."""
    match = re.search(r"\\caption\{", text)
    if not match:
        return ""
    start = match.end()
    depth = 1
    end = start
    while end < len(text) and depth > 0:
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
        end += 1
    return text[start : end - 1]


def is_caption_complete(text: str) -> bool:
    """Check if a caption starting with \\caption{ has balanced braces."""
    match = re.search(r"\\caption\{", text)
    if not match:
        return True  # No caption to check
    start = match.end()
    depth = 1
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        if depth == 0:
            return True
    return False


def parse_file_for_translation(
    content: str,
    is_main_file: bool = False,
    task_id_start: int = 0,
) -> FileParseResult:
    """Parse file and collect translation tasks (no actual translation).

    Args:
        content: File content to parse.
        is_main_file: Whether this is the main file with preamble.
        task_id_start: Starting task_id for global uniqueness.

    Returns:
        FileParseResult with parsed structure and tasks.
    """
    result_parts: list[str | TranslationTask] = []
    tasks: list[TranslationTask] = []
    lines = content.split("\n")
    next_task_id = task_id_start

    # Track environments - separate caption-able envs from others
    caption_envs = ["figure", "table"]
    skip_envs = [
        "equation",
        "align",
        "gather",
        "lstlisting",
        "algorithm",
        "tabular",
        "minipage",
        "adjustbox",
        "center",
        "tcolorbox",
        "tikzpicture",
    ]
    all_envs = caption_envs + skip_envs
    env_depth = {env: 0 for env in all_envs}

    current_para: list[str] = []
    in_document = not is_main_file  # If main file, wait for \begin{document}

    # Caption tasks for concurrent translation
    # (index, original_lines, task) - original_lines is a list for multi-line captions
    caption_tasks: list[tuple[int, list[str], TranslationTask]] = []

    # State for accumulating multi-line captions
    caption_accumulator: list[str] = []
    in_caption = False

    def in_any_skip_env():
        return any(env_depth[env] > 0 for env in all_envs)

    def in_caption_env():
        return any(env_depth[env] > 0 for env in caption_envs)

    def flush_paragraph():
        """Process accumulated paragraph - collect task instead of translating."""
        nonlocal current_para, next_task_id
        if not current_para:
            return

        para_text = "\n".join(current_para)
        result_parts.extend(current_para)

        # Check if paragraph should be translated
        clean_para = clean_for_translation(para_text)
        if is_translatable_paragraph(clean_para):
            # Create task with placeholder
            task = TranslationTask(
                task_id=next_task_id,
                index=len(result_parts),
                clean_text=clean_para,
            )
            next_task_id += 1
            tasks.append(task)
            result_parts.append(task)  # Placeholder for translation
            result_parts.append("")  # Empty line after translation

        current_para = []

    # Parse and collect translation tasks
    for line in lines:
        stripped = line.strip()

        # Track \begin{document} and \end{document}
        if r"\begin{document}" in stripped:
            in_document = True
            result_parts.append(line)
            continue
        if r"\end{document}" in stripped:
            flush_paragraph()
            in_document = False
            result_parts.append(line)
            continue

        # If not in document body (preamble), just copy line
        if not in_document:
            result_parts.append(line)
            continue

        # Track environment depth
        for env in all_envs:
            if re.search(r"\\begin\{" + env + r"\*?\}", stripped):
                env_depth[env] += 1
            if re.search(r"\\end\{" + env + r"\*?\}", stripped):
                env_depth[env] = max(0, env_depth[env] - 1)

        # If in skip environment, handle specially
        if in_any_skip_env():
            flush_paragraph()

            # Handle multi-line caption accumulation
            if in_caption:
                caption_accumulator.append(line)
                combined = "\n".join(caption_accumulator)
                if is_caption_complete(combined):
                    # Caption is complete, process it
                    caption_content = extract_caption_content(combined)
                    if caption_content and len(caption_content) >= 10:
                        clean_caption = clean_for_translation(caption_content)
                        if len(clean_caption) >= 10:
                            task = TranslationTask(
                                task_id=next_task_id,
                                index=len(result_parts),
                                clean_text=clean_caption,
                            )
                            next_task_id += 1
                            tasks.append(task)
                            caption_tasks.append(
                                (len(result_parts), list(caption_accumulator), task)
                            )
                            result_parts.append(task)  # Placeholder
                        else:
                            # Too short after cleaning, just output original lines
                            result_parts.extend(caption_accumulator)
                    else:
                        # Too short, just output original lines
                        result_parts.extend(caption_accumulator)
                    in_caption = False
                    caption_accumulator = []
                continue

            # Check if caption starts on this line
            if in_caption_env() and "\\caption{" in line:
                if is_caption_complete(line):
                    # Single-line caption
                    caption_content = extract_caption_content(line)
                    if caption_content and len(caption_content) >= 10:
                        clean_caption = clean_for_translation(caption_content)
                        if len(clean_caption) >= 10:
                            task = TranslationTask(
                                task_id=next_task_id,
                                index=len(result_parts),
                                clean_text=clean_caption,
                            )
                            next_task_id += 1
                            tasks.append(task)
                            caption_tasks.append((len(result_parts), [line], task))
                            result_parts.append(task)  # Placeholder
                            continue
                else:
                    # Multi-line caption starts here
                    in_caption = True
                    caption_accumulator = [line]
                    continue

            result_parts.append(line)
            continue

        # Check for section headers
        if re.match(r"\\(section|subsection|subsubsection)\{", stripped):
            flush_paragraph()
            result_parts.append(line)
            continue

        # Empty line = paragraph break
        if not stripped:
            flush_paragraph()
            result_parts.append(line)
            continue

        # Comment line
        if stripped.startswith("%"):
            flush_paragraph()
            result_parts.append(line)
            continue

        # Accumulate paragraph
        current_para.append(line)

    flush_paragraph()

    return FileParseResult(
        result_parts=result_parts,
        tasks=tasks,
        caption_tasks=caption_tasks,
    )


def assemble_translated_file(
    parse_result: FileParseResult,
    translations: dict[int, str],
) -> str:
    """Assemble final content with translations.

    Args:
        parse_result: The parsed file structure.
        translations: Dict mapping task_id -> translated text.

    Returns:
        Final assembled file content.
    """
    # Build set of caption task indices for special handling
    # orig_lines is now a list[str] for multi-line caption support
    caption_task_map = {t.index: (orig_lines, t) for _, orig_lines, t in parse_result.caption_tasks}

    final_parts: list[str] = []
    for part in parse_result.result_parts:
        if isinstance(part, TranslationTask):
            translated = translations.get(part.task_id, "")
            if part.index in caption_task_map:
                # Caption: output original lines + translation after the caption
                orig_lines, _ = caption_task_map[part.index]
                final_parts.extend(orig_lines)
                if translated:
                    escaped = escape_for_latex(translated)
                    final_parts.append("    \\trans{" + escaped + "}")
            else:
                # Regular paragraph translation
                if translated:
                    escaped = escape_for_latex(translated)
                    final_parts.append("")
                    final_parts.append(r"\trans{" + escaped + "}")
        else:
            final_parts.append(part)

    return "\n".join(final_parts)


def translate_section_file(
    content: str, is_main_file: bool = False, output_dir: Path | None = None
) -> str:
    """Translate a section file, adding Chinese translation after each paragraph.

    This is a convenience function that combines parsing, translation, and assembly.
    For global parallel translation, use parse_file_for_translation() and
    assemble_translated_file() separately.
    """
    # Parse file
    parse_result = parse_file_for_translation(content, is_main_file)

    # Batch translate
    cfg = get_config()
    max_workers = cfg.max_workers if cfg else 10
    translations = batch_translate(parse_result.tasks, output_dir, max_workers)

    # Assemble result
    return assemble_translated_file(parse_result, translations)
