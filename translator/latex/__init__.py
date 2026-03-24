"""LaTeX processing utilities."""

from translator.latex.cjk import add_cjk_support, add_toc_lot_lof
from translator.latex.engine import (
    TexEngine,
    add_font_fallbacks_to_file,
    detect_engine,
    get_compile_command,
    get_engine_sequence,
    install_packages,
    is_unrecoverable_error,
    parse_missing_fonts,
    parse_missing_packages,
)
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
    "add_toc_lot_lof",
    "add_font_fallbacks_to_file",
    "TexEngine",
    "detect_engine",
    "get_compile_command",
    "get_engine_sequence",
    "install_packages",
    "is_unrecoverable_error",
    "parse_missing_fonts",
    "parse_missing_packages",
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
