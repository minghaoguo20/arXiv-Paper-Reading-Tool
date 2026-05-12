"""LaTeX processing utilities."""

from translator.latex.cjk import add_cjk_support, add_lot_lof, add_toc
from translator.latex.engine import (
    TexEngine,
    add_font_fallbacks_to_file,
    detect_engine,
    get_compile_command,
    install_packages,
    parse_missing_fonts,
    parse_missing_packages,
)
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
    "add_lot_lof",
    "add_toc",
    "add_font_fallbacks_to_file",
    "TexEngine",
    "detect_engine",
    "get_compile_command",
    "install_packages",
    "parse_missing_fonts",
    "parse_missing_packages",
    "FileParseResult",
    "assemble_translated_file",
    "clean_for_translation",
    "escape_for_latex",
    "extract_caption_content",
    "is_translatable_paragraph",
    "parse_file_for_translation",
    "translate_section_file",
]
