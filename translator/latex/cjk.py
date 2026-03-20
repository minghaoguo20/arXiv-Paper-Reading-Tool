"""CJK (Chinese/Japanese/Korean) support for LaTeX documents."""

import re


def add_cjk_support(main_tex_content: str) -> str:
    """Add xeCJK package to main tex file for Chinese support."""
    # First, add hyperref xetex driver option after \documentclass (before hyperref is loaded)
    doc_class_match = re.search(r"(\\documentclass[^\n]*\n)", main_tex_content)
    if doc_class_match:
        # Add xetex option for hyperref before any package loading
        hyperref_fix = r"""
% === XeTeX compatibility (auto-added) ===
\PassOptionsToPackage{xetex}{hyperref}
\PassOptionsToPackage{xetex}{graphicx}
"""
        insert_pos = doc_class_match.end()
        main_tex_content = (
            main_tex_content[:insert_pos] + hyperref_fix + main_tex_content[insert_pos:]
        )

    # Insert xeCJK and fontspec BEFORE \begin{document} to override any font settings
    doc_begin_match = re.search(r"(\\begin\{document\})", main_tex_content)
    if doc_begin_match:
        cjk_config = r"""
% === Chinese Support (auto-added by translator) ===
\usepackage{fontspec}
\usepackage{xeCJK}
\setCJKmainfont{STHeiti}
% Override Times font (ptm) with native Times New Roman
\setmainfont{Times New Roman}[Ligatures=TeX]
\setsansfont{Helvetica}
\setmonofont{Courier New}
% Translation style
\definecolor{transcolor}{gray}{0.4}
\newcommand{\trans}[1]{{\small\color{transcolor}#1}}
% === End Chinese Support ===

"""
        insert_pos = doc_begin_match.start()
        main_tex_content = (
            main_tex_content[:insert_pos] + cjk_config + main_tex_content[insert_pos:]
        )

    return main_tex_content
