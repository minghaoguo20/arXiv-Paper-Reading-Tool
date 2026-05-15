"""LaTeX engine detection and selection."""

import re
import subprocess
from enum import Enum
from pathlib import Path


class TexEngine(Enum):
    """LaTeX engine types."""

    PDFLATEX = "pdflatex"
    XELATEX = "xelatex"



def is_unrecoverable_error(output: str) -> bool:
    """
    Check if the compilation error is unrecoverable (will fail on any engine).

    These are syntax errors or fundamental LaTeX errors that won't be fixed
    by switching engines.

    Args:
        output: Combined stdout/stderr from compilation.

    Returns:
        True if the error is unrecoverable.
    """
    # If error is due to missing packages, it's potentially recoverable
    # by switching engines (the other engine might have the package)
    if re.search(r"File `[^']+\.(sty|cls)' not found", output):
        return False

    unrecoverable_patterns = [
        # Syntax errors
        r"Runaway argument",
        r"Missing \\\$ inserted",
        r"Extra \}, or forgotten \\\$",
        r"Missing \{ inserted",
        r"Missing \} inserted",
        r"Undefined control sequence.*\\begin\{document\}",
        r"Too many \}'s",
        r"Extra alignment tab",
        # Environment errors
        r"\\begin\{[^}]+\} ended by \\end\{[^}]+\}",
        r"Environment .* undefined",
        # File errors that won't be fixed by engine switch
        r"File `[^']+\.tex' not found",
        # Fatal errors (but NOT "Emergency stop" alone - could be from missing package)
        r"Fatal error occurred",
    ]

    for pattern in unrecoverable_patterns:
        if re.search(pattern, output):
            return True

    return False


def detect_engine(output_dir: Path) -> TexEngine:
    """
    Detect the appropriate LaTeX engine for a document.

    Checks for pdfLaTeX-specific features. If found, uses pdfLaTeX.
    Otherwise defaults to XeLaTeX (more modern, better Unicode support).

    Args:
        output_dir: Directory containing tex files.

    Returns:
        TexEngine indicating which engine to use.
    """
    all_tex_files = list(output_dir.glob("**/*.tex"))
    all_cls_files = list(output_dir.glob("**/*.cls"))
    all_sty_files = list(output_dir.glob("**/*.sty"))

    all_content = ""
    for tex_file in all_tex_files + all_cls_files + all_sty_files:
        try:
            all_content += tex_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

    # Check for explicit engine declaration
    if re.search(r"%\s*!TEX\s+program\s*=\s*pdflatex", all_content, re.IGNORECASE):
        return TexEngine.PDFLATEX
    if re.search(r"%\s*!TEX\s+program\s*=\s*xelatex", all_content, re.IGNORECASE):
        return TexEngine.XELATEX
    if re.search(r"%\s*!TEX\s+program\s*=\s*lualatex", all_content, re.IGNORECASE):
        return TexEngine.XELATEX

    # Respect existing CJK package choices as unambiguous engine signals
    if re.search(r"\\usepackage[^{]*\{CJKutf8\}", all_content):
        return TexEngine.PDFLATEX

    # Check for XeLaTeX-specific packages (these won't work with pdfLaTeX)
    xelatex_indicators = [
        r"\\usepackage\{fontspec\}",
        r"\\usepackage\{xeCJK\}",
        r"\\usepackage\{ctex\}",
        r"\\documentclass[^{]*\{ctex",  # ctexart, ctexrep, ctexbook
        r"\\setmainfont",
        r"\\setsansfont",
        r"\\setmonofont",
        r"\\setCJKmainfont",
    ]
    for pattern in xelatex_indicators:
        if re.search(pattern, all_content):
            return TexEngine.XELATEX

    # Check for pdfLaTeX-specific features
    pdflatex_indicators = [
        r"\\usepackage\[T1\]\{fontenc\}",
        r"\\usepackage\[utf8\]\{inputenc\}",
        r"\\DeclareUnicodeCharacter",
        r"\\pdfoutput\s*=\s*1",
        r"\\pdfinfo",
        r"\\pdfcatalog",
        r"\\pdfliteral",
        r"\\pdfcompresslevel",
    ]
    pdflatex_score = 0
    for pattern in pdflatex_indicators:
        if re.search(pattern, all_content):
            pdflatex_score += 1

    # If document has multiple pdfLaTeX-specific features, use pdfLaTeX
    if pdflatex_score >= 2:
        return TexEngine.PDFLATEX

    # Default to XeLaTeX (better Unicode/CJK support)
    return TexEngine.XELATEX


def get_compile_command(engine: TexEngine, tex_file: str) -> list[str]:
    """
    Get the compilation command for the given engine.

    Uses latexmk for automatic multi-pass compilation with BibTeX support.

    Args:
        engine: The TeX engine to use.
        tex_file: Name of the main tex file.

    Returns:
        Command list for subprocess.run.
    """
    if engine == TexEngine.PDFLATEX:
        return [
            "latexmk",
            "-pdf",
            "-bibtex",  # Always run BibTeX for bibliography processing
            "-f",  # Force completion despite errors (warnings won't stop compilation)
            "-interaction=nonstopmode",
            "-file-line-error",
            tex_file,
        ]
    else:  # XeLaTeX
        return [
            "latexmk",
            "-xelatex",
            "-bibtex",  # Always run BibTeX for bibliography processing
            "-f",  # Force completion despite errors (warnings won't stop compilation)
            "-interaction=nonstopmode",
            "-file-line-error",
            tex_file,
        ]


def _find_tlmgr_package(filename: str) -> str | None:
    """
    Find the tlmgr package that contains a given file.

    Args:
        filename: The .sty or .cls file name (without extension).

    Returns:
        The tlmgr package name, or None if not found.
    """
    try:
        result = subprocess.run(
            ["tlmgr", "info", filename],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout + result.stderr

        # Check for direct package match
        for line in output.split("\n"):
            if line.startswith("package:"):
                return line.split(":")[1].strip()

        # Parse "Packages containing files matching" section
        # Format:
        # packagename:
        #     texmf-dist/tex/latex/packagename/file.sty
        current_pkg = None
        for line in output.split("\n"):
            line = line.rstrip()
            # Package name line ends with ':'
            if line and not line.startswith("\t") and line.endswith(":"):
                current_pkg = line[:-1].strip()
            # File path line (indented)
            elif current_pkg and line.startswith("\t"):
                filepath = line.strip()
                # Match tex/latex/package/filename.sty (not lwarp- or tex4ht)
                if f"/{filename}.sty" in filepath or f"/{filename}.cls" in filepath:
                    # Skip wrapper packages like lwarp, tex4ht
                    if "/lwarp/" in filepath or "/tex4ht/" in filepath:
                        continue
                    return current_pkg
    except Exception:
        pass
    return None


def parse_missing_packages(output: str) -> list[str]:
    """
    Parse compiler output to find missing packages.

    Args:
        output: Combined stdout/stderr from latex compilation.

    Returns:
        List of missing package names.
    """
    missing = set()

    # Pattern: ! LaTeX Error: File `xxx.sty' not found.
    # Pattern: ! LaTeX Error: File `xxx.cls' not found.
    for match in re.finditer(r"File `([^']+)\.(sty|cls)' not found", output):
        pkg_name = match.group(1)
        missing.add(pkg_name)

    # Pattern from latexmk: Missing input file 'xxx.sty'
    for match in re.finditer(r"Missing input file '([^']+)\.(sty|cls)'", output):
        pkg_name = match.group(1)
        missing.add(pkg_name)

    # Pattern: Font missing - "! I can't find file `xxx'." or "mktextfm: ... input xxx"
    # These are font files (.tfm, .mf, etc.)
    for match in re.finditer(r"! I can't find file `([^']+)'", output):
        font_name = match.group(1)
        # Map common font file patterns to their package names
        missing.add(_font_to_package(font_name))

    # Pattern: mktexpk: don't know how to create bitmap font for xxx.
    for match in re.finditer(r"don't know how to create bitmap font for (\w+)", output):
        font_name = match.group(1)
        missing.add(_font_to_package(font_name))

    # Remove None values if _font_to_package returned None
    missing.discard(None)

    return list(missing)


def _font_to_package(font_name: str) -> str | None:
    """
    Map a font file name to the package that provides it.

    Args:
        font_name: Font file name (e.g., 'pcrr8t', 'rsfs10').

    Returns:
        Package name or None if unknown.
    """
    # Common font name patterns and their packages
    font_patterns = {
        # Courier fonts (pcr = Postscript Courier)
        r"^pcr": "courier",
        # Times fonts (ptm = Postscript Times)
        r"^ptm": "times",
        # Helvetica fonts (phv = Postscript Helvetica)
        r"^phv": "helvetica",
        # Ralph Smith's Formal Script (rsfs)
        r"^rsfs": "rsfs",
        # Blackboard bold fonts (bbm)
        r"^bbm": "bbm-macros",
        # Computer Modern fonts
        r"^cm": "cm",
        # AMS fonts
        r"^ams": "amsfonts",
        # Euler fonts
        r"^eu": "eulervm",
        # Zapf Dingbats
        r"^pzd": "zapfding",
        # Symbol font
        r"^psy": "symbol",
        # CB Greek fonts (cyber* family)
        r"^cyber": "cbfonts",
        # CJK Unicode bitmap fonts (zhmetrics) → fandol Type1 replacement
        r"^uni(hei|song|fang|kai|zh)": "fandol",
    }

    for pattern, package in font_patterns.items():
        if re.match(pattern, font_name, re.IGNORECASE):
            return package

    # If no pattern matched, return the font name itself
    # (tlmgr might be able to find it)
    return font_name


def parse_missing_fonts(output: str) -> list[str]:
    """
    Parse compiler output to find missing fonts.

    Args:
        output: Combined stdout/stderr from latex compilation.

    Returns:
        List of missing font names (e.g., ['cyberb8f', 'pcrr8t']).
    """
    missing_fonts = set()

    # Pattern 1: pdfTeX error
    # !pdfTeX error: pdflatex (file cyberb8f): Font cyberb8f at 1493 not found
    for match in re.finditer(
        r"pdflatex \(file ([^)]+)\): Font .+ not found", output
    ):
        font_name = match.group(1).strip()
        missing_fonts.add(font_name)

    # Pattern 2: mktexpk error
    # mktexpk: don't know how to create bitmap font for cyberb8f
    for match in re.finditer(
        r"don't know how to create bitmap font for (\w+)", output
    ):
        font_name = match.group(1).strip()
        missing_fonts.add(font_name)

    # Pattern 3: TFM file not found
    # ! I can't find file `cyberb8f.tfm'
    for match in re.finditer(r"! I can't find file `([^']+)\.tfm'", output):
        font_name = match.group(1).strip()
        missing_fonts.add(font_name)

    # Pattern 4: Font not found (generic)
    # Font cyberb8f at 1493 not found
    for match in re.finditer(r"Font (\w+) at \d+ not found", output):
        font_name = match.group(1).strip()
        missing_fonts.add(font_name)

    return list(missing_fonts)


def infer_font_encoding(font_name: str) -> str:
    """
    Infer LaTeX font encoding from font name.

    Args:
        font_name: Font file name (e.g., 'cyberb8f', 'pcrr8t').

    Returns:
        LaTeX encoding name (e.g., 'LGR', 'T1', 'OT1').
    """
    # CJK bitmap fonts - these need special handling, not font fallback
    if font_name.startswith("cyberb"):
        return "C70"
    if re.match(r"^uni(hei|song|fang|kai|zh)", font_name):
        return "C70"

    # CB Greek fonts (grmn*, grml*, but NOT cyberb*)
    if font_name.startswith(("grmn", "grml")):
        return "LGR"

    # T1 encoded fonts
    if font_name.startswith(("pcr", "ptm", "phv", "ec", "ntx", "ptm")):
        return "T1"

    # OMS encoding (math symbols)
    if font_name.startswith(("cmsy", "cmex")):
        return "OMS"

    # Default to OT1 (Computer Modern)
    return "OT1"


def generate_font_fallback(font_name: str) -> str:
    """
    Generate LaTeX font fallback declaration for a missing font.

    Args:
        font_name: Missing font name (e.g., 'cyberb8f').

    Returns:
        LaTeX code declaring font substitutions, or empty string if no fallback possible.
    """
    encoding = infer_font_encoding(font_name)

    # CJK fonts (C70 encoding) cannot be substituted with Computer Modern
    # These need proper CJK font installation or font family mapping
    if encoding == "C70":
        # Return empty - CJK font issues should be fixed by proper font mapping
        # in cjk.py, not by font fallback
        return f"""
% === CJK font {font_name} missing (auto-noted) ===
% CJK fonts require proper installation, cannot substitute with CM
"""

    # Extract font family (usually first 3-4 characters)
    # pcrr8t -> pcr
    if len(font_name) >= 3:
        family = font_name[:4] if font_name[:4].isalpha() else font_name[:3]
    else:
        family = font_name

    # Generate fallback declarations
    fallback = f"""
% === Font fallback for {font_name} (auto-added) ===
\\DeclareFontFamily{{{encoding}}}{{{family}}}{{}}
\\DeclareFontShape{{{encoding}}}{{{family}}}{{m}}{{n}}{{<->ssub*cmr/m/n}}{{}}
\\DeclareFontShape{{{encoding}}}{{{family}}}{{m}}{{it}}{{<->ssub*cmr/m/it}}{{}}
\\DeclareFontShape{{{encoding}}}{{{family}}}{{m}}{{sl}}{{<->ssub*cmr/m/sl}}{{}}
\\DeclareFontShape{{{encoding}}}{{{family}}}{{b}}{{n}}{{<->ssub*cmr/bx/n}}{{}}
\\DeclareFontShape{{{encoding}}}{{{family}}}{{bx}}{{n}}{{<->ssub*cmr/bx/n}}{{}}
\\DeclareFontShape{{{encoding}}}{{{family}}}{{bx}}{{it}}{{<->ssub*cmr/bx/it}}{{}}
"""
    return fallback


def add_font_fallbacks_to_file(main_tex: Path, font_names: list[str]) -> None:
    """
    Add font fallback declarations to main tex file.

    Args:
        main_tex: Path to main tex file.
        font_names: List of missing font names to add fallbacks for.
    """
    if not font_names:
        return

    try:
        content = main_tex.read_text(encoding="utf-8")

        # Build all fallback declarations
        fallbacks = "\n% === Dynamic Font Fallbacks (auto-added) ===\n"
        for font_name in font_names:
            fallbacks += generate_font_fallback(font_name)
        fallbacks += "% === End Dynamic Fallbacks ===\n\n"

        # Insert after \begin{document}
        # This ensures fallbacks are loaded after all packages
        doc_begin_match = re.search(r"(\\begin\{document\})", content)
        if doc_begin_match:
            insert_pos = doc_begin_match.start()
            content = content[:insert_pos] + fallbacks + content[insert_pos:]
            main_tex.write_text(content, encoding="utf-8")
        else:
            # Fallback: insert near the top after \documentclass
            doc_class_match = re.search(r"(\\documentclass[^\n]*\n)", content)
            if doc_class_match:
                insert_pos = doc_class_match.end()
                content = content[:insert_pos] + fallbacks + content[insert_pos:]
                main_tex.write_text(content, encoding="utf-8")

    except Exception as e:
        print(f"  Warning: Failed to add font fallbacks: {e}")


def install_packages(packages: list[str]) -> bool:
    """
    Install LaTeX packages using tlmgr.

    Args:
        packages: List of package names to install.

    Returns:
        True if installation succeeded, False otherwise.
    """
    if not packages:
        return True

    # Map file names to actual tlmgr package names
    pkg_name_map = {
        # zref related
        "zref-abspage": "zref",
        "zref-base": "zref",
        "zref-counter": "zref",
        "zref-lastpage": "zref",
        "zref-user": "zref",
        # Graphics
        "tikz": "pgf",
        # Bibliography
        "bibentry": "natbib",
        # Fonts - newtx family
        "newtxmath": "newtx",
        "newtxtext": "newtx",
        "ntxmath": "newtx",
        # Fonts - psnfss family (PostScript fonts)
        "mathpazo": "psnfss",
        "helvet": "psnfss",
        "courier": "psnfss",
        "times": "psnfss",
        "mathptmx": "psnfss",
        "palatino": "psnfss",
        "bookman": "psnfss",
        "chancery": "psnfss",
        "newcent": "psnfss",
        # Blackboard bold fonts (bbm.sty is in bbm-macros, fonts in bbm)
        "bbm": "bbm-macros",
        # Ralph Smith's Formal Script (rsfs is the correct package name)
        "rsfs": "rsfs",
        # AMS
        "amsfonts": "amsfonts",
        "amssymb": "amsfonts",
        # Tools bundle
        "bm": "tools",
        # Preprint bundle
        "authblk": "preprint",
        "fullpage": "preprint",
        "balance": "preprint",
        # Units
        "nicefrac": "units",
        # Special fonts
        "tipa": "tipa",
        "marvosym": "marvosym",
        "wasysym": "wasysym",
        "pifont": "psnfss",
        "dingbat": "dingbat",
        # Common packages
        "algorithm2e": "algorithm2e",
        "algorithmicx": "algorithmicx",
        "algorithms": "algorithms",
    }

    # Some packages need additional related packages installed together
    extra_deps = {
        "bbm-macros": ["bbm"],  # bbm-macros needs bbm fonts
        "rsfs": ["jknapltx"],  # rsfs may need jknapltx for some features
        "courier": ["psnfss"],  # courier needs psnfss
    }

    # Convert to tlmgr package names, using tlmgr search for unknown packages
    tlmgr_packages = []
    for pkg in packages:
        if pkg in pkg_name_map:
            mapped = pkg_name_map[pkg]
        else:
            # Try to find package using tlmgr info
            mapped = _find_tlmgr_package(pkg) or pkg
        if mapped not in tlmgr_packages:
            tlmgr_packages.append(mapped)
        # Add any extra dependencies
        if mapped in extra_deps:
            for dep in extra_deps[mapped]:
                if dep not in tlmgr_packages:
                    tlmgr_packages.append(dep)

    print(f"  Installing missing packages: {', '.join(tlmgr_packages)}")
    try:
        result = subprocess.run(
            ["tlmgr", "install"] + tlmgr_packages,
            capture_output=True,
            text=True,
            timeout=120,
        )
        # tlmgr may return non-zero even if some packages installed
        return True
    except FileNotFoundError:
        print("  Warning: tlmgr not found, cannot auto-install packages")
        return False
    except subprocess.TimeoutExpired:
        print("  Warning: Package installation timed out")
        return False
    except Exception as e:
        print(f"  Warning: Package installation failed: {e}")
        return False
