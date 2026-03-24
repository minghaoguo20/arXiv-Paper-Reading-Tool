"""CJK (Chinese/Japanese/Korean) support for LaTeX documents."""

import re

from translator.latex.engine import TexEngine


def add_cjk_support(
    main_tex_content: str,
    engine: TexEngine,
    arxiv_id: str | None = None,
    published_date: str | None = None,
    category: str | None = None,
) -> str:
    """
    Add CJK package to main tex file for Chinese support.

    Args:
        main_tex_content: The content of the main tex file.
        engine: The TeX engine to use (determines which CJK package to add).
        arxiv_id: Optional arXiv ID for watermark (e.g., "2511.05271v4").
        published_date: Optional publication date for watermark (e.g., "5 Nov 2025").
        category: Optional arXiv category (e.g., "cs.CL").

    Returns:
        Modified tex content with CJK support and optional watermark.
    """
    if engine == TexEngine.XELATEX:
        return _add_xelatex_cjk_support(
            main_tex_content, arxiv_id, published_date, category
        )
    else:
        return _add_pdflatex_cjk_support(
            main_tex_content, arxiv_id, published_date, category
        )


def _add_xelatex_cjk_support(
    main_tex_content: str,
    arxiv_id: str | None = None,
    published_date: str | None = None,
    category: str | None = None,
) -> str:
    """Add xeCJK support for XeLaTeX engine."""
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

    # Build watermark packages if needed
    watermark_packages = ""
    if arxiv_id and published_date:
        watermark_packages = r"""
% === arXiv Watermark Packages (auto-added) ===
\usepackage{tikz}
\usepackage{eso-pic}
"""

    # Insert xeCJK and fontspec BEFORE \begin{document} to override any font settings
    doc_begin_match = re.search(r"(\\begin\{document\})", main_tex_content)
    if doc_begin_match:
        cjk_config = rf"""
% === Chinese Support (auto-added by translator) ===
\usepackage{{fontspec}}
\usepackage{{xeCJK}}
\setCJKmainfont{{PingFang SC}}
% Override Times font (ptm) with native Times New Roman
\setmainfont{{Times New Roman}}[Ligatures=TeX]
\setsansfont{{Helvetica}}
\setmonofont{{Courier New}}
% Translation style
\definecolor{{transcolor}}{{gray}}{{0.4}}
\newcommand{{\trans}}[1]{{{{\small\color{{transcolor}}#1}}}}
{watermark_packages}% === End Chinese Support ===

"""
        insert_pos = doc_begin_match.start()
        main_tex_content = (
            main_tex_content[:insert_pos] + cjk_config + main_tex_content[insert_pos:]
        )

    # Add watermark code after \begin{document} if metadata is provided
    if arxiv_id and published_date:
        main_tex_content = _add_watermark(
            main_tex_content, arxiv_id, published_date, category
        )

    return main_tex_content


def _add_pdflatex_cjk_support(
    main_tex_content: str,
    arxiv_id: str | None = None,
    published_date: str | None = None,
    category: str | None = None,
) -> str:
    """Add CJKutf8 support for pdfLaTeX engine."""
    # Build watermark packages if needed
    watermark_packages = ""
    if arxiv_id and published_date:
        watermark_packages = r"""
% === arXiv Watermark Packages (auto-added) ===
\usepackage{tikz}
\usepackage{eso-pic}
"""

    # Insert CJKutf8 BEFORE \begin{document}
    doc_begin_match = re.search(r"(\\begin\{document\})", main_tex_content)
    if doc_begin_match:
        cjk_config = rf"""
% === Chinese Support (auto-added by translator) ===
\usepackage{{CJKutf8}}

% === CJK Font Mappings for pdfLaTeX (auto-added) ===
% Map common font families to gbsn to avoid fallback to song/cyberb
\DeclareFontFamily{{C70}}{{phv}}{{}}
\DeclareFontShape{{C70}}{{phv}}{{m}}{{n}}{{<-> CJK * gbsnu}}{{\CJKnormal}}
\DeclareFontShape{{C70}}{{phv}}{{bx}}{{n}}{{<-> CJKb * gbsnu}}{{\CJKbold}}
\DeclareFontFamily{{C70}}{{ptm}}{{}}
\DeclareFontShape{{C70}}{{ptm}}{{m}}{{n}}{{<-> CJK * gbsnu}}{{\CJKnormal}}
\DeclareFontShape{{C70}}{{ptm}}{{bx}}{{n}}{{<-> CJKb * gbsnu}}{{\CJKbold}}
\DeclareFontFamily{{C70}}{{pcr}}{{}}
\DeclareFontShape{{C70}}{{pcr}}{{m}}{{n}}{{<-> CJK * gbsnu}}{{\CJKnormal}}
\DeclareFontShape{{C70}}{{pcr}}{{bx}}{{n}}{{<-> CJKb * gbsnu}}{{\CJKbold}}
% Suppress font substitution warnings
\pdfsuppresswarningpagegroup=1

% Translation style
\definecolor{{transcolor}}{{gray}}{{0.4}}
\newcommand{{\trans}}[1]{{{{\small\color{{transcolor}}#1}}}}
{watermark_packages}% === End Chinese Support ===

"""
        insert_pos = doc_begin_match.start()
        main_tex_content = (
            main_tex_content[:insert_pos] + cjk_config + main_tex_content[insert_pos:]
        )

    # Wrap document body with CJK environment
    # Add \begin{CJK}{UTF8}{gbsn} after \begin{document}
    doc_begin_match = re.search(r"(\\begin\{document\})", main_tex_content)
    if doc_begin_match:
        cjk_begin = r"""
\begin{CJK}{UTF8}{gbsn}
"""
        insert_pos = doc_begin_match.end()
        main_tex_content = (
            main_tex_content[:insert_pos] + cjk_begin + main_tex_content[insert_pos:]
        )

    # Add \end{CJK} before \end{document}
    doc_end_match = re.search(r"(\\end\{document\})", main_tex_content)
    if doc_end_match:
        cjk_end = r"""
\end{CJK}
"""
        insert_pos = doc_end_match.start()
        main_tex_content = (
            main_tex_content[:insert_pos] + cjk_end + main_tex_content[insert_pos:]
        )

    # Add watermark code after \begin{document} and CJK begin if metadata is provided
    if arxiv_id and published_date:
        main_tex_content = _add_watermark(
            main_tex_content, arxiv_id, published_date, category
        )

    return main_tex_content


def _add_watermark(
    content: str,
    arxiv_id: str,
    published_date: str,
    category: str | None,
) -> str:
    """Add arXiv watermark after \\begin{document}."""
    # Build watermark label
    cat_str = f" [{category}]" if category else ""
    watermark_label = f"arXiv:{arxiv_id}{cat_str} {published_date}"

    watermark_code = rf"""
% === arXiv Watermark (auto-added) ===
\AddToShipoutPictureBG*{{%
  \begin{{tikzpicture}}[remember picture, overlay]
    \node[
      text=gray!40,
      font=\Huge\sffamily,
      rotate=90,
      anchor=south west
    ] at ([xshift=16mm, yshift=80mm]current page.south west)
      {{{watermark_label}}};
  \end{{tikzpicture}}
}}
% === End arXiv Watermark ===
"""
    # Insert after \begin{document} (and after CJK begin if present)
    # Look for CJK begin first
    cjk_begin_match = re.search(r"(\\begin\{CJK\}\{UTF8\}\{gbsn\}\n)", content)
    if cjk_begin_match:
        insert_pos = cjk_begin_match.end()
    else:
        doc_begin_match = re.search(r"(\\begin\{document\})", content)
        if doc_begin_match:
            insert_pos = doc_begin_match.end()
        else:
            return content

    return content[:insert_pos] + watermark_code + content[insert_pos:]


def add_toc_lot_lof(content: str) -> str:
    """
    Add Table of Contents, List of Tables, and List of Figures at the end of document.

    Uses \\phantomsection to ensure hyperref links to correct pages.
    Each section starts on a new page with \\clearpage.

    Skips insertion if any of these commands already exist in the document.
    """
    # Skip if TOC/LOT/LOF already exists
    if re.search(r"\\tableofcontents\b", content):
        return content
    if re.search(r"\\listoftables\b", content):
        return content
    if re.search(r"\\listoffigures\b", content):
        return content

    toc_code = r"""
% === Table of Contents, List of Tables/Figures (auto-added) ===
\clearpage
\tableofcontents

\clearpage
\phantomsection
\addcontentsline{toc}{section}{List of Tables}
\listoftables

\clearpage
\phantomsection
\addcontentsline{toc}{section}{List of Figures}
\listoffigures
% === End TOC/LOT/LOF ===
"""
    # Find \end{document} and insert before it
    end_doc_match = re.search(r"(\\end\{document\})", content)
    if end_doc_match:
        insert_pos = end_doc_match.start()
        content = content[:insert_pos] + toc_code + "\n" + content[insert_pos:]

    return content
