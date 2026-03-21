"""LaTeX engine detection and selection."""

import re
import subprocess
from enum import Enum
from pathlib import Path


class TexEngine(Enum):
    """LaTeX engine types."""

    PDFLATEX = "pdflatex"
    XELATEX = "xelatex"


def get_engine_sequence(output_dir: Path, engine_mode: str) -> list[TexEngine]:
    """
    Get the sequence of engines to try based on user preference.

    Args:
        output_dir: Directory containing tex files.
        engine_mode: User-specified engine mode: "auto", "xelatex", or "pdflatex".

    Returns:
        List of engines to try in order.
    """
    if engine_mode == "xelatex":
        return [TexEngine.XELATEX]
    elif engine_mode == "pdflatex":
        return [TexEngine.PDFLATEX]
    else:  # auto mode
        # Check for explicit pdflatex declaration in document
        detected = detect_engine(output_dir)
        if detected == TexEngine.PDFLATEX:
            # Document explicitly uses pdflatex features, try pdflatex first
            return [TexEngine.PDFLATEX, TexEngine.XELATEX]
        else:
            # Default: XeLaTeX first (better CJK), fallback to pdfLaTeX
            return [TexEngine.XELATEX, TexEngine.PDFLATEX]


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
        r"Emergency stop",
        # Fatal errors
        r"Fatal error occurred",
        r"No pages of output",
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
        # LuaLaTeX is closer to XeLaTeX in features
        return TexEngine.XELATEX

    # Check for XeLaTeX-specific packages (these won't work with pdfLaTeX)
    xelatex_indicators = [
        r"\\usepackage\{fontspec\}",
        r"\\usepackage\{xeCJK\}",
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
        r"\\pdfinfo",
        r"\\pdfcatalog",
        r"\\pdfliteral",
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

    Uses latexmk for automatic multi-pass compilation.

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
            "-interaction=nonstopmode",
            "-file-line-error",
            tex_file,
        ]
    else:  # XeLaTeX
        return [
            "latexmk",
            "-xelatex",
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
    }

    for pattern, package in font_patterns.items():
        if re.match(pattern, font_name, re.IGNORECASE):
            return package

    # If no pattern matched, return the font name itself
    # (tlmgr might be able to find it)
    return font_name


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
