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
    get_engine_sequence,
    install_packages,
    is_unrecoverable_error,
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


def _reset_output_dir(paper_dir: Path, output_dir: Path) -> None:
    """
    Reset output directory while preserving translation cache.

    Args:
        paper_dir: Original paper directory.
        output_dir: Output directory to reset.
    """
    cache_dir = output_dir / ".translations"
    cache_backup = None

    # Backup cache if it exists
    if cache_dir.exists():
        cache_backup = paper_dir.parent / f".translations_backup_{paper_dir.name}"
        if cache_backup.exists():
            shutil.rmtree(cache_backup)
        shutil.copytree(cache_dir, cache_backup)

    # Reset output directory
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(paper_dir, output_dir)

    # Restore cache
    if cache_backup and cache_backup.exists():
        shutil.copytree(cache_backup, output_dir / ".translations")
        shutil.rmtree(cache_backup)


def _compile_with_engine(
    output_dir: Path, main_tex: Path, engine: TexEngine
) -> tuple[bool, str]:
    """
    Compile document with specified engine.

    Args:
        output_dir: Directory containing the document.
        main_tex: Path to main tex file.
        engine: LaTeX engine to use.

    Returns:
        Tuple of (success, error_output).
    """
    compile_cmd = get_compile_command(engine, main_tex.name)
    max_attempts = 20
    installed_packages: set[str] = set()
    last_output = ""

    for attempt in range(max_attempts):
        try:
            result = subprocess.run(
                compile_cmd,
                cwd=output_dir,
                capture_output=True,
                text=True,
                timeout=300,
                errors="replace",
            )
            pdf_path = output_dir / (main_tex.stem + ".pdf")
            xdv_path = output_dir / (main_tex.stem + ".xdv")

            # Check if PDF was generated
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                print(f"✓ PDF generated: {pdf_path}")
                subprocess.run(["open", str(output_dir)])
                return True, ""

            # For XeLaTeX, try converting .xdv to PDF
            if (
                engine == TexEngine.XELATEX
                and xdv_path.exists()
                and xdv_path.stat().st_size > 0
            ):
                print("  Converting XDV to PDF...")
                try:
                    subprocess.run(
                        ["xdvipdfmx", "-o", pdf_path.name, xdv_path.name],
                        cwd=output_dir,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if pdf_path.exists() and pdf_path.stat().st_size > 0:
                        print(f"✓ PDF generated: {pdf_path}")
                        subprocess.run(["open", str(output_dir)])
                        return True, ""
                except Exception:
                    pass

            if result.returncode != 0:
                last_output = result.stdout + result.stderr
                missing = parse_missing_packages(last_output)
                new_missing = [pkg for pkg in missing if pkg not in installed_packages]

                if new_missing and attempt < max_attempts - 1:
                    if install_packages(new_missing):
                        installed_packages.update(new_missing)
                        if "-g" not in compile_cmd:
                            compile_cmd.insert(1, "-g")
                        print(f"  Retrying compilation (attempt {attempt + 2})...")
                        continue

                # Check one more time if PDF exists
                if pdf_path.exists() and pdf_path.stat().st_size > 0:
                    print(f"✓ PDF generated (with warnings): {pdf_path}")
                    subprocess.run(["open", str(output_dir)])
                    return True, ""

                return False, last_output

        except subprocess.TimeoutExpired:
            return False, "Compilation timed out"
        except FileNotFoundError:
            return False, "latexmk not found"
        except Exception as e:
            return False, str(e)

    return False, last_output


def _process_with_engine(
    paper_dir: Path,
    output_dir: Path,
    engine: TexEngine,
    cfg: "Config | None",
    metadata: dict | None,
    is_retry: bool = False,
) -> tuple[bool, str]:
    """
    Process paper with a specific engine.

    Args:
        paper_dir: Original paper directory.
        output_dir: Output directory.
        engine: LaTeX engine to use.
        cfg: Configuration object.
        metadata: arXiv metadata.
        is_retry: Whether this is a retry with a different engine.

    Returns:
        Tuple of (success, error_output).
    """
    if is_retry:
        print(f"\n{'='*50}")
        print(f"Retrying with {engine.value}...")
        print(f"{'='*50}")
        _reset_output_dir(paper_dir, output_dir)

    # Fix common package conflicts (engine-aware)
    print("Checking for package conflicts...")
    fix_package_conflicts(output_dir, engine)

    # Find main tex file
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
        return False, "No main tex file found"

    # Add CJK support
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

    # Find included files
    visited: set[Path] = set()
    included_files = find_included_files(main_tex, output_dir, visited)

    # === Phase 1: Parse all files ===
    from translator.latex.parser import FileParseResult

    all_tasks = []
    file_results: dict[Path, FileParseResult] = {}
    task_id_counter = 0

    print(f"Parsing main file: {main_tex.name}")
    content = main_tex.read_text(encoding="utf-8", errors="replace")
    result = parse_file_for_translation(
        content, is_main_file=True, task_id_start=task_id_counter
    )
    result.file_path = main_tex
    file_results[main_tex] = result
    all_tasks.extend(result.tasks)
    task_id_counter += len(result.tasks)

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

    # === Phase 2: Batch translate ===
    max_workers = cfg.max_workers if cfg else 10
    translations = batch_translate(all_tasks, output_dir, max_workers)

    # === Phase 3: Assemble files ===
    print("Assembling translated files...")
    for file_path, parse_result in file_results.items():
        final_content = assemble_translated_file(parse_result, translations)
        file_path.write_text(final_content, encoding="utf-8")

    # === Phase 4: Compile ===
    print(f"\nCompiling with {engine.value}...")
    return _compile_with_engine(output_dir, main_tex, engine)


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

    # Detect source file's preferred engine
    detected_engine = detect_engine(output_dir)
    # Color codes: bold yellow for pdflatex hint, bold cyan for xelatex hint
    if detected_engine == TexEngine.PDFLATEX:
        color = "\033[1;33m"  # Bold Yellow
        hint = "pdfLaTeX features detected (fontenc, inputenc, etc.)"
    else:
        color = "\033[1;36m"  # Bold Cyan
        hint = "XeLaTeX compatible (default)"
    print(f"Source analysis: {color}[{detected_engine.value}]\033[0m - {hint}")

    # Get engine sequence based on user preference
    engine_mode = cfg.engine if cfg else "auto"
    if engine_mode == "auto":
        # In auto mode, always start with XeLaTeX (better CJK support)
        engines = [TexEngine.XELATEX]
        print(f"Engine: \033[1;32m[xelatex]\033[0m (default, best for CJK)")
    else:
        engines = get_engine_sequence(output_dir, engine_mode)
        print(f"Engine: \033[1;32m[{engine_mode}]\033[0m (user specified)")

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

    # Try first engine
    current_engine = engines[0]
    success, error_output = _process_with_engine(
        paper_dir, output_dir, current_engine, cfg, metadata, is_retry=False
    )

    # If failed and in auto mode, ask user whether to try pdfLaTeX
    if not success and engine_mode == "auto" and current_engine == TexEngine.XELATEX:
        # Check for unrecoverable errors first
        if is_unrecoverable_error(error_output):
            print(f"\n\033[1;31m[Unrecoverable error detected (syntax error, etc.)]\033[0m")
            print(error_output[-2000:] if len(error_output) > 2000 else error_output)
        else:
            print(f"\n\033[1;33m[XeLaTeX compilation failed]\033[0m")
            print("Error summary:")
            # Show last 500 chars of error
            print(error_output[-500:] if len(error_output) > 500 else error_output)
            print()

            # Ask user whether to try pdfLaTeX
            try:
                response = input("\033[1;36m[Try pdfLaTeX instead?] [y/N]: \033[0m").strip().lower()
                if response == "y":
                    success, error_output = _process_with_engine(
                        paper_dir, output_dir, TexEngine.PDFLATEX, cfg, metadata, is_retry=True
                    )
                    if not success:
                        print(f"\n\033[1;31m[pdfLaTeX also failed]\033[0m")
                        print(error_output[-2000:] if len(error_output) > 2000 else error_output)
                else:
                    print("Skipped pdfLaTeX fallback.")
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")

    elif not success:
        # User specified engine failed
        print(f"\n\033[1;31m[Compilation failed ({current_engine.value})]\033[0m")
        if error_output == "latexmk not found":
            print("Error: latexmk not found. Please install TinyTeX or BasicTeX:")
            print("  TinyTeX: curl -sL 'https://yihui.org/tinytex/install-bin-unix.sh' | sh")
            print("  BasicTeX: brew install --cask basictex")
        else:
            print(error_output[-2000:] if len(error_output) > 2000 else error_output)

    print(f"\nOutput directory: {output_dir}")
