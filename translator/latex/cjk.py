"""CJK (Chinese/Japanese/Korean) support for LaTeX documents."""

import re


def add_cjk_support(
    main_tex_content: str,
    arxiv_id: str | None = None,
    published_date: str | None = None,
    category: str | None = None,
) -> str:
    """
    Add xeCJK package to main tex file for Chinese support.

    Args:
        main_tex_content: The content of the main tex file.
        arxiv_id: Optional arXiv ID for watermark (e.g., "2511.05271v4").
        published_date: Optional publication date for watermark (e.g., "5 Nov 2025").
        category: Optional arXiv category (e.g., "cs.CL").

    Returns:
        Modified tex content with CJK support and optional watermark.
    """
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
        # Insert after \begin{document}
        doc_begin_match = re.search(r"(\\begin\{document\})", main_tex_content)
        if doc_begin_match:
            insert_pos = doc_begin_match.end()
            main_tex_content = (
                main_tex_content[:insert_pos]
                + watermark_code
                + main_tex_content[insert_pos:]
            )

    return main_tex_content
