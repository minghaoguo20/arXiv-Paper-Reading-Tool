"""LaTeX document parsing and translation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from arxiv_latex_cleaner.arxiv_latex_cleaner import (
    _remove_command,
    _remove_comments_inline,
    _remove_environment,
    _simplify_conditional_blocks,
)

from papercli.translate.api import TranslationTask, batch_translate

if TYPE_CHECKING:
    from papercli.translate.config import TranslateConfig


@dataclass
class FileParseResult:
    """Result of parsing a file for translation."""

    file_path: Path = field(default_factory=lambda: Path())
    result_parts: list[str | TranslationTask] = field(default_factory=list)
    tasks: list[TranslationTask] = field(default_factory=list)
    # (index, original_lines, task) - original_lines is list[str] for multi-line captions
    caption_tasks: list[tuple[int, list[str], TranslationTask]] = field(default_factory=list)


def get_config() -> "TranslateConfig | None":
    from papercli.translate.config import TranslateConfig

    return TranslateConfig._instance


def sanitize_line(line: str) -> str:
    """Sanitize a line for bilingual output.

    Applies transformations to avoid layout conflicts in translated documents:
    - Convert wrapfigure to figure (text wrapping conflicts with translations)
    - Remove negative vspace (causes overlap when content increases)
    """
    line = re.sub(
        r"\\begin\{wrapfigure\}\[[^\]]*\]\{[^}]*\}\{[^}]*\}",
        r"\\begin{figure}[!ht]",
        line,
    )
    line = re.sub(
        r"\\begin\{wrapfigure\}\{[^}]*\}\{[^}]*\}",
        r"\\begin{figure}[!ht]",
        line,
    )
    line = re.sub(r"\\end\{wrapfigure\}", r"\\end{figure}", line)
    line = re.sub(r"\\vspace\{-[^}]*\}", "", line)

    return line


def is_translatable_paragraph(text: str) -> bool:
    """Check if a text block should be translated."""
    text = text.strip()
    if len(text) < 30:
        return False
    if text.count("\\") > len(text) / 10:
        return False
    if re.match(r"^\\[a-zA-Z]+(\{[^}]*\}|\[[^\]]*\])*$", text):
        return False
    return True


def clean_for_translation(text: str) -> tuple[str, dict[str, str]]:
    """Clean LaTeX text before translation, removing commands but keeping content.

    Returns:
        Tuple of (cleaned_text, refs_map) where refs_map maps placeholders to original LaTeX.
    """
    refs_map: dict[str, str] = {}

    ESCAPED_DOLLAR_PLACEHOLDER = "\x00DOLLAR\x00"

    text = text.replace(r"\$", ESCAPED_DOLLAR_PLACEHOLDER)

    math_matches = re.findall(r"\$[^$]+\$", text)
    for i, match in enumerate(math_matches):
        original_match = match.replace(ESCAPED_DOLLAR_PLACEHOLDER, r"\$")
        placeholder = f"[MATH_{i}]"
        refs_map[placeholder] = original_match
        text = text.replace(match, placeholder, 1)

    inline_paren_matches = re.findall(r"\\\(.*?\\\)", text, re.DOTALL)
    for match in inline_paren_matches:
        original_match = match.replace(ESCAPED_DOLLAR_PLACEHOLDER, r"\$")
        placeholder = f"[MATH_{len(refs_map)}]"
        refs_map[placeholder] = original_match
        text = text.replace(match, placeholder, 1)

    display_bracket_matches = re.findall(r"\\\[.*?\\\]", text, re.DOTALL)
    for match in display_bracket_matches:
        original_match = match.replace(ESCAPED_DOLLAR_PLACEHOLDER, r"\$")
        placeholder = f"[MATH_{len(refs_map)}]"
        refs_map[placeholder] = original_match
        text = text.replace(match, placeholder, 1)

    text = text.replace(ESCAPED_DOLLAR_PLACEHOLDER, r"\$")

    cite_matches = re.findall(r"~?\\cite[pt]?\s*\{[^}]*\}", text)
    for i, match in enumerate(cite_matches):
        placeholder = f"[CITE_{i}]"
        refs_map[placeholder] = match
        text = text.replace(match, placeholder, 1)

    ref_matches = re.findall(r"~?\\ref\s*\{[^}]*\}", text)
    for i, match in enumerate(ref_matches):
        placeholder = f"[REF_{i}]"
        refs_map[placeholder] = match
        text = text.replace(match, placeholder, 1)

    def extract_footnotes(text: str) -> list[str]:
        """Extract all \\footnote{...} commands handling nested braces."""
        matches = []
        pos = 0
        while True:
            match = re.search(r"\\footnote\{", text[pos:])
            if not match:
                break
            start = pos + match.start()
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
                break
            matches.append(text[start:i])
            pos = i
        return matches

    footnote_matches = extract_footnotes(text)
    for i, match in enumerate(footnote_matches):
        placeholder = f"[FOOTNOTE_{i}]"
        refs_map[placeholder] = match
        text = text.replace(match, placeholder, 1)

    def extract_textcolor(text: str) -> list[str]:
        """Extract all \\textcolor{...}{...} commands handling nested braces."""
        matches = []
        pattern = r"\\textcolor(?:\[[^\]]*\])?\{"
        pos = 0
        while True:
            match = re.search(pattern, text[pos:])
            if not match:
                break
            start = pos + match.start()
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
                break
            color_end = i
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
                break
            full_match = text[start:i]
            matches.append(full_match)
            pos = i
        return matches

    textcolor_matches = extract_textcolor(text)
    for i, match in enumerate(textcolor_matches):
        placeholder = f"[TEXTCOLOR_{i}]"
        refs_map[placeholder] = match
        text = text.replace(match, placeholder, 1)

    macro_matches = sorted(set(re.findall(r"\\[a-zA-Z]+(?![{a-zA-Z])", text)), key=len, reverse=True)
    for i, match in enumerate(macro_matches):
        placeholder = f"[MACRO_{i}]"
        refs_map[placeholder] = match
        text = text.replace(match, placeholder)

    text = re.sub(r"\\begin\{[^}]+\}(\[[^\]]*\])?", "", text)
    text = re.sub(r"\\end\{[^}]+\}", "", text)
    text = re.sub(r"\\item(\[[^\]]*\])?", "", text)
    text = re.sub(r"\\label\{[^}]*\}", "", text)
    text = _remove_command(text, "textit", keep_text=True)
    text = _remove_command(text, "textbf", keep_text=True)
    text = _remove_command(text, "emph", keep_text=True)
    text = re.sub(r"\s+", " ", text)
    return text.strip(), refs_map


def restore_refs(text: str, refs_map: dict[str, str]) -> str:
    """Restore original LaTeX references from placeholders."""
    for placeholder, original in refs_map.items():
        text = text.replace(placeholder, original)
        escaped_placeholder = placeholder.replace("_", r"\_")
        text = text.replace(escaped_placeholder, original)
    return text


def escape_for_latex(text: str) -> str:
    """Escape special characters in translated text for LaTeX."""
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = text.replace("{", "").replace("}", "")
    text = text.replace("\\", "")
    text = text.replace("$", r"\$")
    text = text.replace("%", r"\%")
    text = text.replace("&", r"\&")
    text = text.replace("#", r"\#")
    text = text.replace("_", r"\_")
    text = text.replace("^", "")
    text = text.replace("~", " ")
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
        return True
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
    lines_with_ends = content.splitlines(keepends=True)
    lines_with_ends = [_remove_comments_inline(line) for line in lines_with_ends]
    content = _remove_environment("".join(lines_with_ends), "comment")
    content = _simplify_conditional_blocks(content)

    result_parts: list[str | TranslationTask] = []
    tasks: list[TranslationTask] = []
    lines = content.split("\n")
    next_task_id = task_id_start

    caption_envs = [
        "figure",
        "figure*",
        "table",
        "table*",
        "wraptable",
        "longtable",
        "tabularx",
        "tabulary",
        "supertabular",
        "xtabular",
    ]
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
        "thebibliography",
    ]
    all_envs = caption_envs + skip_envs
    env_depth = {env: 0 for env in all_envs}

    current_para: list[str] = []
    in_document = not is_main_file
    after_maketitle = not is_main_file
    in_abstract = False
    pending_item_prefix: str | None = None

    caption_tasks: list[tuple[int, list[str], TranslationTask]] = []

    caption_accumulator: list[str] = []
    in_caption = False
    in_abstract_cmd = False
    abstract_cmd_depth = 0
    abstract_cmd_para: list[str] = []

    def in_any_skip_env():
        return any(env_depth[env] > 0 for env in all_envs)

    def in_caption_env():
        return any(env_depth[env] > 0 for env in caption_envs)

    def flush_paragraph():
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

        clean_para, refs_map = clean_for_translation(para_text)
        if is_translatable_paragraph(clean_para):
            task = TranslationTask(
                task_id=next_task_id,
                index=len(result_parts),
                clean_text=clean_para,
                refs_map=refs_map,
            )
            next_task_id += 1
            tasks.append(task)
            result_parts.append(task)
            result_parts.append("")

        current_para = []

    for line in lines:
        line = sanitize_line(line)
        stripped = line.strip()

        if r"\begin{document}" in stripped:
            in_document = True
            result_parts.append(line)
            continue
        if r"\end{document}" in stripped:
            flush_paragraph()
            in_document = False
            result_parts.append(line)
            continue

        if r"\maketitle" in stripped:
            after_maketitle = True
            result_parts.append(line)
            continue

        if r"\begin{abstract}" in stripped:
            in_abstract = True
        if r"\end{abstract}" in stripped:
            flush_paragraph()
            in_abstract = False
            after_maketitle = True

        # Handle \abstract{...} command form (e.g., ustc_conference class)
        if not in_abstract_cmd and re.search(r'\\abstract\{', stripped):
            in_abstract_cmd = True
            abstract_cmd_para = []
            match = re.search(r'\\abstract\{', line)
            result_parts.append(line[:match.end()])
            rest = line[match.end():]
            depth = 1
            close_at = None
            for i, ch in enumerate(rest):
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        close_at = i
                        break
            if close_at is not None:
                content_here = rest[:close_at].rstrip()
                if content_here:
                    abstract_cmd_para.append(content_here)
                if abstract_cmd_para:
                    para_text = "\n".join(abstract_cmd_para)
                    result_parts.extend(abstract_cmd_para)
                    clean_para, refs_map = clean_for_translation(para_text)
                    if is_translatable_paragraph(clean_para):
                        task = TranslationTask(
                            task_id=next_task_id,
                            index=len(result_parts),
                            clean_text=clean_para,
                            refs_map=refs_map,
                        )
                        next_task_id += 1
                        tasks.append(task)
                        result_parts.append(task)
                        result_parts.append("")
                result_parts.append('}' + rest[close_at + 1:])
                in_abstract_cmd = False
            else:
                abstract_cmd_depth = depth
                if rest.strip():
                    abstract_cmd_para.append(rest.rstrip())
            continue

        if in_abstract_cmd:
            depth = abstract_cmd_depth
            close_at = None
            for i, ch in enumerate(line):
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        close_at = i
                        break
            if close_at is not None:
                content_here = line[:close_at].rstrip()
                if content_here:
                    abstract_cmd_para.append(content_here)
                if abstract_cmd_para:
                    para_text = "\n".join(abstract_cmd_para)
                    result_parts.extend(abstract_cmd_para)
                    clean_para, refs_map = clean_for_translation(para_text)
                    if is_translatable_paragraph(clean_para):
                        task = TranslationTask(
                            task_id=next_task_id,
                            index=len(result_parts),
                            clean_text=clean_para,
                            refs_map=refs_map,
                        )
                        next_task_id += 1
                        tasks.append(task)
                        result_parts.append(task)
                        result_parts.append("")
                result_parts.append('}' + line[close_at + 1:])
                in_abstract_cmd = False
            else:
                abstract_cmd_depth = depth
                abstract_cmd_para.append(line)
            continue

        if not in_abstract and (not in_document or not after_maketitle):
            result_parts.append(line)
            continue

        if stripped.startswith("%"):
            flush_paragraph()
            result_parts.append(line)
            continue

        for env in all_envs:
            env_pattern = re.escape(env)
            if re.search(r"\\begin\{" + env_pattern + r"\}", stripped):
                env_depth[env] += 1
            if re.search(r"\\end\{" + env_pattern + r"\}", stripped):
                env_depth[env] = max(0, env_depth[env] - 1)

        if in_any_skip_env():
            flush_paragraph()

            if in_caption:
                caption_accumulator.append(line)
                combined = "\n".join(caption_accumulator)
                if is_caption_complete(combined):
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
                            result_parts.append(task)
                        else:
                            result_parts.extend(caption_accumulator)
                    else:
                        result_parts.extend(caption_accumulator)
                    in_caption = False
                    caption_accumulator = []
                continue

            if in_caption_env() and "\\caption{" in line:
                if is_caption_complete(line):
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
                            result_parts.append(task)
                            continue
                else:
                    in_caption = True
                    caption_accumulator = [line]
                    continue

            result_parts.append(line)
            continue

        if re.match(r"\\(section|subsection|subsubsection|paragraph)\*?\{", stripped):
            flush_paragraph()
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

        if re.search(r"\\(?:begin|end)\{(?:enumerate|itemize|description)\*?\}", stripped):
            flush_paragraph()
            result_parts.append(line)
            continue

        item_match = re.match(r"^(\s*\\item(?:\[[^\]]*\])?)\s*(.*)", line, re.DOTALL)
        if item_match:
            flush_paragraph()
            pending_item_prefix = item_match.group(1)
            item_body = item_match.group(2).strip()
            if item_body:
                current_para.append(item_body)
            continue

        if re.match(r"\\input\{[^}]*\}", stripped):
            flush_paragraph()
            result_parts.append(line)
            continue

        if not stripped:
            flush_paragraph()
            result_parts.append(line)
            continue

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
    caption_task_map = {t.index: (orig_lines, t) for _, orig_lines, t in parse_result.caption_tasks}

    final_parts: list[str] = []
    for part in parse_result.result_parts:
        if isinstance(part, TranslationTask):
            translated = translations.get(part.task_id, "")
            if part.index in caption_task_map:
                orig_lines, _ = caption_task_map[part.index]
                if translated:
                    escaped = escape_for_latex(translated)
                    restored = restore_refs(escaped, part.refs_map)
                    trans_text = " \\trans{" + restored + "}"

                    combined = "\n".join(orig_lines)

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

                        modified = combined[:end-1] + trans_text + combined[end-1:]
                        final_parts.extend(modified.split("\n"))
                    else:
                        final_parts.extend(orig_lines)
                else:
                    final_parts.extend(orig_lines)
            else:
                if translated:
                    escaped = escape_for_latex(translated)
                    restored = restore_refs(escaped, part.refs_map)
                    final_parts.append(r"\\\trans{" + restored + "}")
        else:
            final_parts.append(part)

    return "\n".join(final_parts)


def translate_section_file(
    content: str, is_main_file: bool = False, output_dir: Path | None = None
) -> str:
    """Translate a section file (convenience wrapper combining parse + translate + assemble)."""
    parse_result = parse_file_for_translation(content, is_main_file)

    cfg = get_config()
    max_workers = cfg.max_workers if cfg else 10
    translations = batch_translate(parse_result.tasks, output_dir, max_workers)

    return assemble_translated_file(parse_result, translations)
