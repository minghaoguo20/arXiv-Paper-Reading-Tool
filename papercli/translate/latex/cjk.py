"""CJK (Chinese/Japanese/Korean) support for LaTeX documents."""

import re

from papercli.translate.latex.engine import TexEngine


def add_cjk_support(
    main_tex_content: str,
    engine: TexEngine,
    arxiv_id: str | None = None,
    published_date: str | None = None,
    category: str | None = None,
    trans_gray: float = 0.4,
    trans_fontsize: str = "",
    font_xelatex: str = "PingFang SC",
    font_lualatex: str = "PingFang SC",
    font_pdflatex: str = "gbsn",
) -> str:
    if "% === Chinese Support (auto-added by translator) ===" in main_tex_content:
        return main_tex_content
    if engine == TexEngine.XELATEX:
        return _add_xelatex_cjk_support(
            main_tex_content, arxiv_id, published_date, category, trans_gray, trans_fontsize, font_xelatex
        )
    elif engine == TexEngine.LUALATEX:
        return _add_lualatex_cjk_support(
            main_tex_content, arxiv_id, published_date, category, trans_gray, trans_fontsize, font_lualatex
        )
    else:
        return _add_pdflatex_cjk_support(
            main_tex_content, arxiv_id, published_date, category, trans_gray, trans_fontsize, font_pdflatex
        )


def _add_xelatex_cjk_support(
    main_tex_content: str,
    arxiv_id: str | None = None,
    published_date: str | None = None,
    category: str | None = None,
    trans_gray: float = 0.4,
    trans_fontsize: str = "",
    font: str = "PingFang SC",
) -> str:
    """Add xeCJK support for XeLaTeX engine."""
    watermark_packages = ""
    if arxiv_id and published_date:
        watermark_packages = r"""
% === arXiv Watermark Packages (auto-added) ===
\usepackage{tikz}
\usepackage{eso-pic}
"""

    size_cmd = f"\\{trans_fontsize}" if trans_fontsize and trans_fontsize != "normal" else ""
    doc_begin_match = re.search(r"(\\begin\{document\})", main_tex_content)
    if doc_begin_match:
        cjk_config = rf"""
% === Chinese Support (auto-added by translator) ===
\usepackage{{xeCJK}}
\setCJKmainfont{{{font}}}
\usepackage{{xcolor}}
\definecolor{{transcolor}}{{gray}}{{{trans_gray}}}
\newcommand{{\trans}}[1]{{{{{size_cmd}\color{{transcolor}}#1}}}}
{watermark_packages}% === End Chinese Support ===

"""
        insert_pos = doc_begin_match.start()
        main_tex_content = (
            main_tex_content[:insert_pos] + cjk_config + main_tex_content[insert_pos:]
        )

    if arxiv_id and published_date:
        main_tex_content = _add_watermark(
            main_tex_content, arxiv_id, published_date, category
        )

    return main_tex_content


def _add_lualatex_cjk_support(
    main_tex_content: str,
    arxiv_id: str | None = None,
    published_date: str | None = None,
    category: str | None = None,
    trans_gray: float = 0.4,
    trans_fontsize: str = "",
    font: str = "PingFang SC",
) -> str:
    """Add luatexja CJK support for LuaLaTeX engine."""
    watermark_packages = ""
    if arxiv_id and published_date:
        watermark_packages = r"""
% === arXiv Watermark Packages (auto-added) ===
\usepackage{tikz}
\usepackage{eso-pic}
"""

    size_cmd = f"\\{trans_fontsize}" if trans_fontsize and trans_fontsize != "normal" else ""
    doc_begin_match = re.search(r"(\\begin\{document\})", main_tex_content)
    if doc_begin_match:
        cjk_config = rf"""
% === Chinese Support (auto-added by translator) ===
\usepackage{{luatexja}}
\usepackage{{luatexja-fontspec}}
\setmainjfont{{{font}}}
\usepackage{{xcolor}}
\definecolor{{transcolor}}{{gray}}{{{trans_gray}}}
\newcommand{{\trans}}[1]{{{{{size_cmd}\color{{transcolor}}#1}}}}
{watermark_packages}% === End Chinese Support ===

"""
        insert_pos = doc_begin_match.start()
        main_tex_content = (
            main_tex_content[:insert_pos] + cjk_config + main_tex_content[insert_pos:]
        )

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
    trans_gray: float = 0.4,
    trans_fontsize: str = "",
    font: str = "gbsn",
) -> str:
    """Add CJKutf8 support for pdfLaTeX engine."""
    watermark_packages = ""
    if arxiv_id and published_date:
        watermark_packages = r"""
% === arXiv Watermark Packages (auto-added) ===
\usepackage{tikz}
\usepackage{eso-pic}
"""

    # Disable microtype font expansion before \documentclass so that classes
    # loading microtype via \RequirePackage don't apply expansion to CJK bitmap fonts,
    # which causes "auto expansion is only possible with scalable fonts" fatal errors.
    docclass_match = re.search(r"(\\documentclass)", main_tex_content)
    if docclass_match and r"\PassOptionsToPackage{expansion=false}{microtype}" not in main_tex_content:
        main_tex_content = (
            main_tex_content[:docclass_match.start()]
            + "\\PassOptionsToPackage{expansion=false}{microtype}\n"
            + main_tex_content[docclass_match.start():]
        )

    size_cmd = f"\\{trans_fontsize}" if trans_fontsize and trans_fontsize != "normal" else ""
    doc_begin_match = re.search(r"(\\begin\{document\})", main_tex_content)
    if doc_begin_match:
        cjk_config = rf"""
% === Chinese Support (auto-added by translator) ===
\usepackage{{CJKutf8}}
\usepackage{{xcolor}}
\definecolor{{transcolor}}{{gray}}{{{trans_gray}}}
\newcommand{{\trans}}[1]{{{{{size_cmd}\color{{transcolor}}#1}}}}
{watermark_packages}% === End Chinese Support ===

"""
        insert_pos = doc_begin_match.start()
        main_tex_content = (
            main_tex_content[:insert_pos] + cjk_config + main_tex_content[insert_pos:]
        )

    doc_begin_match = re.search(r"(\\begin\{document\})", main_tex_content)
    if doc_begin_match:
        insert_pos = doc_begin_match.end()
        main_tex_content = (
            main_tex_content[:insert_pos]
            + f"\n\\begin{{CJK*}}{{UTF8}}{{{font}}}"
            + main_tex_content[insert_pos:]
        )

    if arxiv_id and published_date:
        main_tex_content = _add_watermark(
            main_tex_content, arxiv_id, published_date, category
        )

    end_doc_match = re.search(r"(\\end\{document\})", main_tex_content)
    if end_doc_match:
        insert_pos = end_doc_match.start()
        main_tex_content = (
            main_tex_content[:insert_pos]
            + "\\end{CJK*}\n"
            + main_tex_content[insert_pos:]
        )

    return main_tex_content


def _add_watermark(
    content: str,
    arxiv_id: str,
    published_date: str,
    category: str | None,
) -> str:
    """Add arXiv watermark after \\begin{document}."""
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


def add_toc(content: str) -> str:
    """Add Table of Contents at the end of document. Skips if already present."""
    if re.search(r"\\tableofcontents\b", content):
        return content

    toc_code = r"""
% === Table of Contents (auto-added) ===
\clearpage
\phantomsection
\tableofcontents
% === End TOC ===
"""
    end_doc_match = re.search(r"(\\end\{document\})", content)
    if end_doc_match:
        insert_pos = end_doc_match.start()
        content = content[:insert_pos] + toc_code + "\n" + content[insert_pos:]

    return content


def add_lot_lof(content: str) -> str:
    """Add List of Tables and List of Figures at the end of document."""
    if re.search(r"\\listoftables\b", content):
        return content
    if re.search(r"\\listoffigures\b", content):
        return content

    lot_lof_code = r"""
% === List of Tables/Figures (auto-added) ===
\phantomsection
\addcontentsline{toc}{section}{List of Tables}
\listoftables

\phantomsection
\addcontentsline{toc}{section}{List of Figures}
\listoffigures
% === End LOT/LOF ===
"""
    end_doc_match = re.search(r"(\\end\{document\})", content)
    if end_doc_match:
        insert_pos = end_doc_match.start()
        content = content[:insert_pos] + lot_lof_code + "\n" + content[insert_pos:]

    return content
