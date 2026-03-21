"""LaTeX package conflict fixes."""

import re
from pathlib import Path


def fix_package_conflicts(output_dir: Path) -> None:
    """Fix common LaTeX package conflicts across the entire project."""
    # Collect all tex content to detect project-wide conflicts
    all_tex_files = list(output_dir.glob("**/*.tex"))
    all_content = ""
    for tex_file in all_tex_files:
        try:
            all_content += tex_file.read_text(encoding="utf-8")
        except Exception:
            continue

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

    # Fix pdfLaTeX-only commands that don't work in XeTeX
    # \DeclareUnicodeCharacter is provided by inputenc and not available in XeTeX
    # \usepackage{unicode} is a rare/custom package not available in tectonic
    # microtype tracking option only works with pdfTeX
    for tex_file in all_tex_files:
        try:
            content = tex_file.read_text(encoding="utf-8", errors="replace")
            original = content
            # Comment out \DeclareUnicodeCharacter (pdfLaTeX only, XeTeX handles Unicode natively)
            content = re.sub(
                r"(\\DeclareUnicodeCharacter\{[^}]*\}\{[^}]*\})",
                r"% \1 % commented: XeTeX handles Unicode natively",
                content,
            )
            # Comment out \usepackage{unicode} (rare package, XeTeX has native Unicode support)
            content = re.sub(
                r"(\\usepackage\{unicode\})",
                r"% \1 % commented: XeTeX handles Unicode natively",
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
            # Remove tracking option from microtype (tracking=... only works with pdfTeX)
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
    # Check for any CJK-related packages
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
