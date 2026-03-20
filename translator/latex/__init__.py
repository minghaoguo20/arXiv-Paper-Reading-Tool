"""LaTeX processing utilities."""

from translator.latex.cjk import add_cjk_support
from translator.latex.fixes import fix_package_conflicts
from translator.latex.parser import (
    FileParseResult,
    assemble_translated_file,
    clean_for_translation,
    escape_for_latex,
    extract_caption_content,
    is_translatable_paragraph,
    parse_file_for_translation,
    translate_section_file,
)

__all__ = [
    "add_cjk_support",
    "fix_package_conflicts",
    "FileParseResult",
    "assemble_translated_file",
    "clean_for_translation",
    "escape_for_latex",
    "extract_caption_content",
    "is_translatable_paragraph",
    "parse_file_for_translation",
    "translate_section_file",
]
