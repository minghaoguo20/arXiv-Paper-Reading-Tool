"""LaTeX package conflict fixes."""

import re
from pathlib import Path

from translator.latex.engine import TexEngine


def fix_package_conflicts(output_dir: Path, engine: TexEngine) -> None:
    """
    Fix common LaTeX package conflicts across the entire project.

    Some fixes are engine-specific (only needed for XeTeX or pdfLaTeX).

    Args:
        output_dir: Directory containing tex files.
        engine: The TeX engine being used.
    """
    # Collect all tex content to detect project-wide conflicts
    all_tex_files = list(output_dir.glob("**/*.tex"))
    all_cls_files = list(output_dir.glob("**/*.cls"))
    all_sty_files = list(output_dir.glob("**/*.sty"))
    all_files = all_tex_files + all_cls_files + all_sty_files

    all_content = ""
    for tex_file in all_tex_files:
        try:
            all_content += tex_file.read_text(encoding="utf-8")
        except Exception:
            continue

    # === Engine-independent fixes ===

    # Check for subfigure/subcaption conflict project-wide
    has_subfigure = r"\usepackage{subfigure}" in all_content
    has_subcaption = r"\usepackage{subcaption}" in all_content

    if has_subfigure and has_subcaption:
        # Comment out all subfigure uses (subcaption is newer and preferred)
        for tex_file in all_tex_files:
            try:
                content = tex_file.read_text(encoding="utf-8")
                if r"\usepackage{subfigure}" in content:
                    content = content.replace(
                        r"\usepackage{subfigure}",
                        r"%\usepackage{subfigure} % commented: conflicts with subcaption",
                    )
                    tex_file.write_text(content, encoding="utf-8")
                    print(f"  Fixed subfigure/subcaption conflict in {tex_file.name}")
            except Exception:
                continue

    # Fix natbib with unsrt/plain bibliographystyle (needs numbers option)
    for tex_file in all_tex_files:
        try:
            content = tex_file.read_text(encoding="utf-8")
            # If using natbib without options and numeric bibliographystyle
            if r"\usepackage{natbib}" in content:
                if re.search(
                    r"\\bibliographystyle\{(unsrt|plain|abbrv|ieeetr|acm)\}", content
                ):
                    content = content.replace(
                        r"\usepackage{natbib}", r"\usepackage[numbers]{natbib}"
                    )
                    tex_file.write_text(content, encoding="utf-8")
                    print(f"  Fixed natbib citation style in {tex_file.name}")
        except Exception:
            continue

    # === pdfLaTeX-specific fixes ===
    if engine == TexEngine.PDFLATEX:
        _apply_pdflatex_fixes(all_files, all_content)

    # === XeTeX-specific fixes ===
    # These are only needed when using XeLaTeX engine

    if engine == TexEngine.XELATEX:
        _apply_xelatex_fixes(output_dir, all_tex_files, all_content)


def _apply_xelatex_fixes(
    output_dir: Path, all_tex_files: list[Path], all_content: str
) -> None:
    """Apply fixes specific to XeLaTeX engine."""

    # Fix pdfLaTeX-only commands that don't work in XeTeX
    for tex_file in all_tex_files:
        try:
            content = tex_file.read_text(encoding="utf-8", errors="replace")
            original = content

            # Comment out \DeclareUnicodeCharacter (pdfLaTeX only)
            content = re.sub(
                r"(\\DeclareUnicodeCharacter\{[^}]*\}\{[^}]*\})",
                r"% \1 % commented: XeTeX handles Unicode natively",
                content,
            )

            # Comment out \usepackage{unicode} (rare package, not in tectonic/texlive)
            content = re.sub(
                r"(\\usepackage\{unicode\})",
                r"% \1 % commented: XeTeX handles Unicode natively",
                content,
            )

            # Comment out \usepackage[T1]{fontenc} (conflicts with XeTeX font handling)
            content = re.sub(
                r"(\\usepackage\[T1\]\{fontenc\})",
                r"% \1 % commented: XeTeX uses fontspec instead",
                content,
            )

            if content != original:
                tex_file.write_text(content, encoding="utf-8")
                print(f"  Fixed pdfLaTeX-only commands in {tex_file.name}")
        except Exception:
            continue

    # Fix microtype tracking option (only works with pdfTeX, not XeTeX)
    all_cls_files = list(output_dir.glob("**/*.cls"))
    for cls_file in all_tex_files + all_cls_files:
        try:
            content = cls_file.read_text(encoding="utf-8", errors="replace")
            original = content
            # Remove tracking option from microtype
            content = re.sub(
                r"(\\(?:RequirePackage|usepackage))\[tracking=[^\]]*\](\{microtype\})",
                r"\1\2",
                content,
            )
            if content != original:
                cls_file.write_text(content, encoding="utf-8")
                print(f"  Fixed microtype tracking option in {cls_file.name}")
        except Exception:
            continue

    # Replace old CJK package with xeCJK (for XeTeX compatibility)
    has_cjk = re.search(r"\\usepackage\{CJK(utf8)?\}", all_content)
    if has_cjk:
        for tex_file in all_tex_files:
            try:
                content = tex_file.read_text(encoding="utf-8", errors="replace")
                original = content
                # Comment out old CJK packages (CJK, CJKutf8)
                content = re.sub(
                    r"\\usepackage\{CJK(utf8)?\}",
                    r"%\\usepackage{CJK} % replaced by xeCJK",
                    content,
                )
                # Replace \begin{CJK} and \begin{CJK*} variants with empty
                content = re.sub(r"\\begin\{CJK\*?\}\{[^}]*\}\{[^}]*\}", "", content)
                content = re.sub(r"\\end\{CJK\*?\}", "", content)
                if content != original:
                    tex_file.write_text(content, encoding="utf-8")
                    print(f"  Fixed CJK usage in {tex_file.name}")
            except Exception:
                continue


def _apply_pdflatex_fixes(all_files: list[Path], all_content: str) -> None:
    """Apply fixes specific to pdfLaTeX engine."""

    # Check if document uses non-scalable fonts (rsfs, bbm, etc.)
    # that conflict with microtype's font expansion feature
    non_scalable_fonts = [
        r"\\usepackage\{rsfs\}",
        r"\\usepackage\{mathrsfs\}",  # Math Ralph Smith's Formal Script
        r"\\usepackage\{calrsfs\}",  # Calligraphic rsfs
        r"\\usepackage\{bbm\}",
        r"\\mathscr",  # Often uses rsfs
        r"\\mathbbm",  # Uses bbm
    ]

    has_non_scalable = any(
        re.search(pattern, all_content) for pattern in non_scalable_fonts
    )

    if has_non_scalable:
        # Disable microtype expansion to avoid font conflicts
        for file_path in all_files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                original = content

                # Replace \usepackage{microtype} with expansion disabled
                # Match both with and without options
                content = re.sub(
                    r"\\usepackage(\[[^\]]*\])?\{microtype\}",
                    r"\\usepackage[expansion=false]{microtype}",
                    content,
                )

                if content != original:
                    file_path.write_text(content, encoding="utf-8")
                    print(f"  Fixed microtype expansion in {file_path.name}")
            except Exception:
                continue
