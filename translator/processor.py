"""Paper processing and PDF generation."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from translator.api import batch_translate
from translator.arxiv import get_arxiv_metadata
from translator.latex import (
    TexEngine,
    add_cjk_support,
    assemble_translated_file,
    detect_engine,
    fix_package_conflicts,
    get_compile_command,
    install_packages,
    parse_file_for_translation,
    parse_missing_packages,
)

if TYPE_CHECKING:
    from translator.cli import Config


def get_config() -> "Config | None":
    """Get the current Config instance."""
    from translator.cli import Config

    return Config._instance


def extract_arxiv_id_from_path(paper_dir: Path) -> str | None:
    """
    Extract arXiv ID from paper directory name.

    Directory names are typically like:
    - arXiv-2511.05271v4
    - 2511.05271v4
    - 2511.05271

    Returns:
        arXiv ID string or None if not found.
    """
    name = paper_dir.name

    # Pattern for arXiv ID: YYMM.NNNNN or YYMM.NNNNNvN
    arxiv_pattern = r"(\d{4}\.\d{4,5}(?:v\d+)?)"
    match = re.search(arxiv_pattern, name)

    if match:
        return match.group(1)
    return None


def is_preamble_file(filepath: Path) -> bool:
    """Check if a file is a preamble/config file (should not be translated)."""
    name = filepath.stem.lower()
    # Skip by filename
    if any(
        skip in name
        for skip in ["config", "preamble", "header", "macro", "command", "setup"]
    ):
        return True
    # Check content - if mostly \usepackage/\def/\newcommand, it's preamble
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        lines = [
            line.strip()
            for line in content.split("\n")
            if line.strip() and not line.strip().startswith("%")
        ]
        if not lines:
            return True
        preamble_cmds = sum(
            1
            for line in lines
            if re.match(
                r"\\(usepackage|RequirePackage|def|newcommand|renewcommand|setlength|definecolor)",
                line,
            )
        )
        # If more than 50% are preamble commands, skip
        if preamble_cmds / len(lines) > 0.5:
            return True
    except Exception:
        pass
    return False


def find_included_files(tex_file: Path, base_dir: Path, visited: set) -> list[Path]:
    """Recursively find all files included via \\input or \\include."""
    if tex_file in visited or not tex_file.exists():
        return []
    visited.add(tex_file)

    included = []
    try:
        content = tex_file.read_text(encoding="utf-8", errors="replace")
        # Find \input{...} and \include{...}
        patterns = [r"\\input\{([^}]+)\}", r"\\include\{([^}]+)\}"]
        for pattern in patterns:
            for match in re.finditer(pattern, content):
                ref = match.group(1).strip()
                # Skip common non-translatable includes
                if any(
                    skip in ref.lower()
                    for skip in ["table", "bib", "sty", "cls", "bbl", "fig"]
                ):
                    continue
                # Add .tex extension if missing
                if not ref.endswith(".tex"):
                    ref += ".tex"
                # Resolve path relative to base_dir
                inc_path = base_dir / ref
                if inc_path.exists() and inc_path not in visited:
                    # Skip preamble/config files
                    if is_preamble_file(inc_path):
                        continue
                    included.append(inc_path)
                    # Recursively find includes in this file
                    included.extend(find_included_files(inc_path, base_dir, visited))
    except Exception:
        pass
    return included


def process_paper(paper_dir: Path) -> None:
    """Process a paper directory and generate bilingual PDF."""
    cfg = get_config()
    print(f"Processing: {paper_dir.name}")

    # Create output directory with copy of paper
    output_dir = paper_dir.parent / f"{paper_dir.name}_bilingual"

    if cfg and cfg.resume and output_dir.exists():
        # Resume mode: keep existing output, reuse cache
        print(f"Resuming translation in {output_dir}")
        cache_dir = output_dir / ".translations"
        if cache_dir.exists():
            cached_count = len(list(cache_dir.glob("*.txt")))
            print(f"  Found {cached_count} cached translations")
    else:
        # Fresh start: remove old and copy new
        if output_dir.exists():
            shutil.rmtree(output_dir)
        shutil.copytree(paper_dir, output_dir)
        print(f"Copied to: {output_dir}")

    # Detect LaTeX engine
    engine = detect_engine(output_dir)
    print(f"Detected engine: {engine.value}")

    # Fix common package conflicts (engine-aware)
    print("Checking for package conflicts...")
    fix_package_conflicts(output_dir, engine)

    # Find main tex file (must contain \documentclass)
    main_tex = None
    tex_files = list(output_dir.glob("*.tex"))
    for tex_file in tex_files:
        try:
            content = tex_file.read_text(encoding="utf-8")
            if r"\documentclass" in content:
                main_tex = tex_file
                break
        except Exception:
            continue
    if main_tex is None:
        raise FileNotFoundError("No main tex file found (no file with \\documentclass)")

    # Get arXiv metadata for watermark
    arxiv_id = extract_arxiv_id_from_path(paper_dir)
    metadata = None
    if arxiv_id:
        print(f"Fetching arXiv metadata for {arxiv_id}...")
        metadata = get_arxiv_metadata(arxiv_id)
        if metadata:
            print(f"  Published: {metadata['published']}")
            if metadata.get("category"):
                print(f"  Category: {metadata['category']}")

    # Add CJK support to main file
    print(f"Adding CJK support to {main_tex.name} ({engine.value})...")
    main_content = main_tex.read_text(encoding="utf-8")
    main_content = add_cjk_support(
        main_content,
        engine=engine,
        arxiv_id=metadata.get("arxiv_id") if metadata else None,
        published_date=metadata.get("published") if metadata else None,
        category=metadata.get("category") if metadata else None,
    )
    main_tex.write_text(main_content, encoding="utf-8")

    # Start from main file and find all included files
    visited: set[Path] = set()
    included_files = find_included_files(main_tex, output_dir, visited)

    # === Phase 1: Parse all files and collect all tasks ===
    from translator.latex.parser import FileParseResult

    all_tasks = []
    file_results: dict[Path, FileParseResult] = {}
    task_id_counter = 0

    # Parse main file
    print(f"Parsing main file: {main_tex.name}")
    content = main_tex.read_text(encoding="utf-8", errors="replace")
    result = parse_file_for_translation(content, is_main_file=True, task_id_start=task_id_counter)
    result.file_path = main_tex
    file_results[main_tex] = result
    all_tasks.extend(result.tasks)
    task_id_counter += len(result.tasks)

    # Parse included files
    if included_files:
        print(f"Parsing {len(included_files)} included files")
        for inc_file in included_files:
            rel_path = inc_file.relative_to(output_dir)
            print(f"  {rel_path}")
            content = inc_file.read_text(encoding="utf-8", errors="replace")
            result = parse_file_for_translation(
                content, is_main_file=False, task_id_start=task_id_counter
            )
            result.file_path = inc_file
            file_results[inc_file] = result
            all_tasks.extend(result.tasks)
            task_id_counter += len(result.tasks)

    print(f"Collected {len(all_tasks)} paragraphs from {len(file_results)} files")

    # === Phase 2: Batch translate all paragraphs concurrently ===
    max_workers = cfg.max_workers if cfg else 10
    translations = batch_translate(all_tasks, output_dir, max_workers)

    # === Phase 3: Assemble and write back each file ===
    print("Assembling translated files...")
    for file_path, parse_result in file_results.items():
        final_content = assemble_translated_file(parse_result, translations)
        file_path.write_text(final_content, encoding="utf-8")

    # Compile with latexmk (with auto-install of missing packages)
    compile_cmd = get_compile_command(engine, main_tex.name)
    print(f"\nCompiling with {engine.value}...")

    max_attempts = 20  # Prevent infinite loop
    installed_packages: set[str] = set()  # Track installed packages to avoid loops

    for attempt in range(max_attempts):
        try:
            result = subprocess.run(
                compile_cmd,
                cwd=output_dir,
                capture_output=True,
                text=True,
                timeout=300,
                errors="replace",  # Handle non-UTF8 output
            )
            pdf_path = output_dir / (main_tex.stem + ".pdf")
            xdv_path = output_dir / (main_tex.stem + ".xdv")

            # Check if PDF was generated (success even with warnings)
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                print(f"✓ PDF generated: {pdf_path}")
                # Open PDF
                subprocess.run(["open", str(output_dir)])
                break

            # For XeLaTeX, .xdv may be generated but not converted to PDF
            # If xdv exists and is recent, try to convert it
            if (
                engine == TexEngine.XELATEX
                and xdv_path.exists()
                and xdv_path.stat().st_size > 0
            ):
                print("  Converting XDV to PDF...")
                try:
                    conv_result = subprocess.run(
                        ["xdvipdfmx", "-o", pdf_path.name, xdv_path.name],
                        cwd=output_dir,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if pdf_path.exists() and pdf_path.stat().st_size > 0:
                        print(f"✓ PDF generated: {pdf_path}")
                        subprocess.run(["open", str(output_dir)])
                        break
                except Exception:
                    pass  # Fall through to error handling

            if result.returncode != 0:
                # Check for missing packages
                output = result.stdout + result.stderr
                missing = parse_missing_packages(output)

                # Filter out packages we've already tried to install
                new_missing = [pkg for pkg in missing if pkg not in installed_packages]

                if new_missing and attempt < max_attempts - 1:
                    if install_packages(new_missing):
                        installed_packages.update(new_missing)
                        # Add -g to force regeneration on retry
                        if "-g" not in compile_cmd:
                            compile_cmd.insert(1, "-g")
                        print(f"  Retrying compilation (attempt {attempt + 2})...")
                        continue

                # No new packages to install or all attempts exhausted
                # Check one more time if PDF exists (might have been generated despite error)
                if pdf_path.exists() and pdf_path.stat().st_size > 0:
                    print(f"✓ PDF generated (with warnings): {pdf_path}")
                    subprocess.run(["open", str(output_dir)])
                    break

                print(f"Compilation failed ({engine.value}):")
                print(output[-2000:] if len(output) > 2000 else output)
                break
        except subprocess.TimeoutExpired:
            print("Compilation timed out")
            break
        except FileNotFoundError:
            print("Error: latexmk not found. Please install TinyTeX or BasicTeX:")
            print("  TinyTeX: curl -sL 'https://yihui.org/tinytex/install-bin-unix.sh' | sh")
            print("  BasicTeX: brew install --cask basictex")
            break
        except Exception as e:
            print(f"Compilation error: {e}")
            break

    print(f"\nOutput directory: {output_dir}")
