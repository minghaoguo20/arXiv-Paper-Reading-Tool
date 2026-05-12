"""LaTeX document parsing and translation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from arxiv_latex_cleaner.arxiv_latex_cleaner import (
    _remove_comments_inline,
    _remove_environment,
)

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


def sanitize_line(line: str) -> str:
    """Sanitize a line for bilingual output.

    Applies transformations to avoid layout conflicts in translated documents:
    - Convert wrapfigure to figure (text wrapping conflicts with translations)
    - Remove negative vspace (causes overlap when content increases)
    """
    # Convert \begin{wrapfigure}... to \begin{figure}[!ht]
    # Handle: \begin{wrapfigure}[lines]{pos}{width} (with optional lines arg)
    line = re.sub(
        r"\\begin\{wrapfigure\}\[[^\]]*\]\{[^}]*\}\{[^}]*\}",
        r"\\begin{figure}[!ht]",
        line,
    )
    # Handle: \begin{wrapfigure}{pos}{width} (without optional arg)
    line = re.sub(
        r"\\begin\{wrapfigure\}\{[^}]*\}\{[^}]*\}",
        r"\\begin{figure}[!ht]",
        line,
    )
    # Convert \end{wrapfigure} to \end{figure}
    line = re.sub(r"\\end\{wrapfigure\}", r"\\end{figure}", line)

    # Remove negative \vspace (e.g., \vspace{-10pt}, \vspace{-2em})
    line = re.sub(r"\\vspace\{-[^}]*\}", "", line)

    return line


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


def clean_for_translation(text: str) -> tuple[str, dict[str, str]]:
    """Clean LaTeX text before translation, removing commands but keeping content.

    Returns:
        Tuple of (cleaned_text, refs_map) where refs_map maps placeholders to original LaTeX.
    """
    refs_map: dict[str, str] = {}

    # Placeholder for escaped dollar signs to prevent false matches
    ESCAPED_DOLLAR_PLACEHOLDER = "\x00DOLLAR\x00"

    # Protect escaped dollar signs (\$) before extraction
    text = text.replace(r"\$", ESCAPED_DOLLAR_PLACEHOLDER)

    # Extract and replace inline math $...$ with unique placeholders
    math_matches = re.findall(r"\$[^$]+\$", text)
    for i, match in enumerate(math_matches):
        # Restore escaped dollars within the match
        original_match = match.replace(ESCAPED_DOLLAR_PLACEHOLDER, r"\$")
        placeholder = f"[MATH_{i}]"
        refs_map[placeholder] = original_match
        text = text.replace(match, placeholder, 1)

    # Extract and replace \(...\) inline math with unique placeholders
    inline_paren_matches = re.findall(r"\\\(.*?\\\)", text, re.DOTALL)
    for match in inline_paren_matches:
        # Restore escaped dollars within the match
        original_match = match.replace(ESCAPED_DOLLAR_PLACEHOLDER, r"\$")
        placeholder = f"[MATH_{len(refs_map)}]"
        refs_map[placeholder] = original_match
        text = text.replace(match, placeholder, 1)

    # Extract and replace \[...\] display math with unique placeholders
    display_bracket_matches = re.findall(r"\\\[.*?\\\]", text, re.DOTALL)
    for match in display_bracket_matches:
        # Restore escaped dollars within the match
        original_match = match.replace(ESCAPED_DOLLAR_PLACEHOLDER, r"\$")
        placeholder = f"[MATH_{len(refs_map)}]"
        refs_map[placeholder] = original_match
        text = text.replace(match, placeholder, 1)

    # Restore escaped dollars in remaining text
    text = text.replace(ESCAPED_DOLLAR_PLACEHOLDER, r"\$")

    # Extract and replace \cite commands with unique placeholders
    cite_matches = re.findall(r"~?\\cite[pt]?\{[^}]*\}", text)
    for i, match in enumerate(cite_matches):
        placeholder = f"[CITE_{i}]"
        refs_map[placeholder] = match
        text = text.replace(match, placeholder, 1)

    # Extract and replace \ref commands with unique placeholders
    ref_matches = re.findall(r"~?\\ref\{[^}]*\}", text)
    for i, match in enumerate(ref_matches):
        placeholder = f"[REF_{i}]"
        refs_map[placeholder] = match
        text = text.replace(match, placeholder, 1)

    # Extract and replace \textcolor{color}{text} commands with unique placeholders
    # This handles commands like \textcolor{blue!70}{text} where color can contain !
    def extract_textcolor(text: str) -> list[str]:
        """Extract all \textcolor{...}{...} commands handling nested braces."""
        matches = []
        pattern = r"\\textcolor\{"
        pos = 0
        while True:
            match = re.search(pattern, text[pos:])
            if not match:
                break
            start = pos + match.start()
            # Find the first argument (color)
            brace_start = pos + match.end()
            depth = 1
            i = brace_start
            while i < len(text) and depth > 0:
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                i += 1
            if depth != 0:
                break  # Unbalanced braces
            color_end = i
            # Find the second argument (text content)
            if color_end >= len(text) or text[color_end] != "{":
                pos = color_end
                continue
            depth = 1
            i = color_end + 1
            while i < len(text) and depth > 0:
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                i += 1
            if depth != 0:
                break  # Unbalanced braces
            # Extract the full command
            full_match = text[start:i]
            matches.append(full_match)
            pos = i
        return matches

    textcolor_matches = extract_textcolor(text)
    for i, match in enumerate(textcolor_matches):
        placeholder = f"[TEXTCOLOR_{i}]"
        refs_map[placeholder] = match
        text = text.replace(match, placeholder, 1)

    # Extract and replace no-arg macros (e.g., \model, \dataset, \LaTeX)
    # Match \xxx not followed by { or letter (to avoid \textbf{...} etc.)
    macro_matches = list(set(re.findall(r"\\[a-zA-Z]+(?![{a-zA-Z])", text)))
    for i, match in enumerate(macro_matches):
        placeholder = f"[MACRO_{i}]"
        refs_map[placeholder] = match
        text = text.replace(match, placeholder)

    # Remove comments (% not preceded by digit or backslash - avoids matching 15% or \%)
    text = re.sub(r"(?<![\d\\])%.*", "", text)
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
    # Clean up whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip(), refs_map


def restore_refs(text: str, refs_map: dict[str, str]) -> str:
    """Restore original LaTeX references from placeholders.

    Args:
        text: Translated text with placeholders.
        refs_map: Mapping from placeholders to original LaTeX.

    Returns:
        Text with placeholders replaced by original LaTeX references.
    """
    for placeholder, original in refs_map.items():
        # Handle both normal and escaped placeholders (e.g., [REF_0] and [REF\_0])
        text = text.replace(placeholder, original)
        escaped_placeholder = placeholder.replace("_", r"\_")
        text = text.replace(escaped_placeholder, original)
    return text


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
    # Strip all LaTeX comments before parsing
    lines_with_ends = content.splitlines(keepends=True)
    lines_with_ends = [_remove_comments_inline(line) for line in lines_with_ends]
    content = _remove_environment("".join(lines_with_ends), "comment")

    result_parts: list[str | TranslationTask] = []
    tasks: list[TranslationTask] = []
    lines = content.split("\n")
    next_task_id = task_id_start

    # Track environments - separate caption-able envs from others
    # caption_envs: Allow \caption{} translation, skip other content
    # Note: wrapfigure is converted to figure by convert_wrapfigure_line()
    caption_envs = [
        "figure",
        "figure*",        # Two-column figure
        "table",
        "table*",         # Two-column table
        "wraptable",      # Wrap table (from wrapfig package)
        "longtable",      # Long tables (multi-page) - has caption inside
        "tabularx",       # Extended tabular - may have caption
        "tabulary",       # Auto-width tabular - may have caption
        "supertabular",   # Another multi-page table - may have caption
        "xtabular",       # Extended tabular - may have caption
    ]
    # skip_envs: Skip everything (no translation at all)
    skip_envs = [
        "equation",
        "align",
        "gather",
        "lstlisting",
        "algorithm",
        "tabular",        # Basic tabular (no caption inside)
        "minipage",
        "adjustbox",
        "center",
        "tcolorbox",
        "tikzpicture",
        "thebibliography",  # Bibliography: contains \bibitem and TeX commands, not translatable
    ]
    all_envs = caption_envs + skip_envs
    env_depth = {env: 0 for env in all_envs}

    current_para: list[str] = []
    in_document = not is_main_file  # If main file, wait for \begin{document}
    after_maketitle = not is_main_file  # If main file, wait for \maketitle
    in_abstract = False  # Track if we're inside abstract environment
    pending_item_prefix: str | None = None  # pending \item prefix to prepend to first body line

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
        nonlocal current_para, next_task_id, pending_item_prefix
        if not current_para:
            if pending_item_prefix is not None:
                result_parts.append(pending_item_prefix)
                pending_item_prefix = None
            return

        if pending_item_prefix is not None:
            combined_lines = [pending_item_prefix + " " + current_para[0]] + current_para[1:]
            pending_item_prefix = None
        else:
            combined_lines = current_para

        para_text = "\n".join(current_para)
        result_parts.extend(combined_lines)

        # Check if paragraph should be translated
        clean_para, refs_map = clean_for_translation(para_text)
        if is_translatable_paragraph(clean_para):
            # Create task with placeholder
            task = TranslationTask(
                task_id=next_task_id,
                index=len(result_parts),
                clean_text=clean_para,
                refs_map=refs_map,
            )
            next_task_id += 1
            tasks.append(task)
            result_parts.append(task)  # Placeholder for translation
            result_parts.append("")  # Empty line after translation

        current_para = []

    # Parse and collect translation tasks
    for line in lines:
        # Sanitize line: convert wrapfigure to figure, remove negative vspace
        line = sanitize_line(line)
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

        # Track \maketitle - start translating after this
        if r"\maketitle" in stripped:
            after_maketitle = True
            result_parts.append(line)
            continue

        # Track abstract environment (should translate even before \maketitle)
        if r"\begin{abstract}" in stripped:
            in_abstract = True
        if r"\end{abstract}" in stripped:
            flush_paragraph()  # Process accumulated content before leaving abstract
            in_abstract = False
            # Also mark as after_maketitle since abstract typically follows title
            # This handles templates that don't use \maketitle (e.g., ICML \twocolumn[...])
            after_maketitle = True

        # If not in document body (preamble) or before \maketitle, just copy line
        # Exception: translate content inside abstract environment
        if not in_abstract and (not in_document or not after_maketitle):
            result_parts.append(line)
            continue

        # Comment line - skip environment tracking for comments
        if stripped.startswith("%"):
            flush_paragraph()
            result_parts.append(line)
            continue

        # Track environment depth
        for env in all_envs:
            # Escape env name for regex (e.g., "figure*" -> "figure\*")
            env_pattern = re.escape(env)
            if re.search(r"\\begin\{" + env_pattern + r"\}", stripped):
                env_depth[env] += 1
            if re.search(r"\\end\{" + env_pattern + r"\}", stripped):
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
                        clean_caption, refs_map = clean_for_translation(caption_content)
                        if len(clean_caption) >= 10:
                            task = TranslationTask(
                                task_id=next_task_id,
                                index=len(result_parts),
                                clean_text=clean_caption,
                                refs_map=refs_map,
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
                        clean_caption, refs_map = clean_for_translation(caption_content)
                        if len(clean_caption) >= 10:
                            task = TranslationTask(
                                task_id=next_task_id,
                                index=len(result_parts),
                                clean_text=clean_caption,
                                refs_map=refs_map,
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

        # Check for section headers (including starred versions like \section*)
        if re.match(r"\\(section|subsection|subsubsection|paragraph)\*?\{", stripped):
            flush_paragraph()
            # Find end of the command's argument (accounting for nested braces),
            # so that any inline text after the closing brace can be accumulated
            # for translation (e.g. \paragraph{Title} Some inline text here.).
            depth = 0
            cmd_end = -1
            for _i, _ch in enumerate(line):
                if _ch == "{":
                    depth += 1
                elif _ch == "}":
                    depth -= 1
                    if depth == 0:
                        cmd_end = _i + 1
                        break
            if cmd_end > 0 and cmd_end < len(line):
                trailing = line[cmd_end:].strip()
                result_parts.append(line[:cmd_end])
                if trailing:
                    current_para.append(trailing)
            else:
                result_parts.append(line)
            continue

        # Check for list environment boundaries - treat as paragraph delimiters so that
        # \begin{enumerate}/\end{enumerate} are never swallowed into a paragraph and end
        # up missing from the output (they cannot legally live inside \trans{}).
        if re.search(r"\\(?:begin|end)\{(?:enumerate|itemize|description)\*?\}", stripped):
            flush_paragraph()
            result_parts.append(line)
            continue

        # Check for \item - flush current paragraph, then accumulate the item body
        # with the \item prefix stored so flush_paragraph can join them on one line.
        item_match = re.match(r"^(\s*\\item(?:\[[^\]]*\])?)\s*(.*)", line, re.DOTALL)
        if item_match:
            flush_paragraph()
            pending_item_prefix = item_match.group(1)
            item_body = item_match.group(2).strip()
            if item_body:
                current_para.append(item_body)  # start new paragraph for item content
            continue

        # Empty line = paragraph break
        if not stripped:
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
                # Caption: insert translation inside \caption{} command
                orig_lines, _ = caption_task_map[part.index]
                if translated:
                    escaped = escape_for_latex(translated)
                    restored = restore_refs(escaped, part.refs_map)
                    trans_text = " \\trans{" + restored + "}"

                    # Combine all original lines to find the caption closing brace
                    combined = "\n".join(orig_lines)

                    # Find the position of the closing brace for \caption{}
                    match = re.search(r"\\caption\{", combined)
                    if match:
                        start = match.end()
                        depth = 1
                        end = start
                        while end < len(combined) and depth > 0:
                            if combined[end] == "{":
                                depth += 1
                            elif combined[end] == "}":
                                depth -= 1
                            end += 1

                        # Insert translation before the closing brace
                        modified = combined[:end-1] + trans_text + combined[end-1:]
                        final_parts.extend(modified.split("\n"))
                    else:
                        # Fallback: just output original lines if no caption found
                        final_parts.extend(orig_lines)
                else:
                    # No translation, just output original lines
                    final_parts.extend(orig_lines)
            else:
                # Regular paragraph translation
                if translated:
                    escaped = escape_for_latex(translated)
                    # Restore refs after escaping (placeholders are not affected by escape)
                    restored = restore_refs(escaped, part.refs_map)
                    final_parts.append(r"\trans{" + restored + "}")
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
