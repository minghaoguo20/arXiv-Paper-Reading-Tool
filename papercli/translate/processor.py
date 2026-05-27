"""Paper processing and PDF generation."""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from papercli.translate.api import batch_translate
from papercli.arxiv import get_arxiv_metadata
from papercli.translate.latex import (
    TexEngine,
    add_cjk_support,
    add_lot_lof,
    add_toc,
    add_font_fallbacks_to_file,
    assemble_translated_file,
    detect_engine,
    get_compile_command,
    install_packages,
    parse_file_for_translation,
    parse_missing_bst_files,
    parse_missing_fonts,
    parse_missing_packages,
)

if TYPE_CHECKING:
    from papercli.translate.config import TranslateConfig


def get_config() -> "TranslateConfig | None":
    from papercli.translate.config import TranslateConfig

    return TranslateConfig._instance


def extract_arxiv_id_from_path(paper_dir: Path) -> str | None:
    """Extract arXiv ID from paper directory name."""
    name = paper_dir.name
    arxiv_pattern = r"(\d{4}\.\d{4,5}(?:v\d+)?)"
    match = re.search(arxiv_pattern, name)
    if match:
        return match.group(1)
    return None


def is_preamble_file(filepath: Path) -> bool:
    """Check if a file is a preamble/config file (should not be translated)."""
    name = filepath.stem.lower()
    if any(
        skip in name
        for skip in ["config", "preamble", "header", "macro", "command", "setup"]
    ):
        return True
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
        patterns = [r"\\input\{([^}]+)\}", r"\\include\{([^}]+)\}"]
        for pattern in patterns:
            for match in re.finditer(pattern, content):
                ref = match.group(1).strip()
                if any(
                    skip in ref.lower()
                    for skip in ["bib", "sty", "cls", "bbl"]
                ):
                    continue
                if not ref.endswith(".tex"):
                    ref += ".tex"
                inc_path = base_dir / ref
                if inc_path.exists() and inc_path not in visited:
                    if is_preamble_file(inc_path):
                        continue
                    included.append(inc_path)
                    included.extend(find_included_files(inc_path, base_dir, visited))
    except Exception:
        pass
    return included


def _reset_output_dir(paper_dir: Path, output_dir: Path) -> None:
    """Reset output directory while preserving translation cache."""
    cache_dir = output_dir / ".translations"
    cache_backup = None

    if cache_dir.exists():
        cache_backup = paper_dir.parent / f".translations_backup_{paper_dir.name}"
        if cache_backup.exists():
            shutil.rmtree(cache_backup)
        shutil.copytree(cache_dir, cache_backup)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(paper_dir, output_dir)

    if cache_backup and cache_backup.exists():
        shutil.copytree(cache_backup, output_dir / ".translations")
        shutil.rmtree(cache_backup)


def _run_latex(cmd: list[str], cwd: Path, timeout: int = 300) -> subprocess.CompletedProcess:
    """Run a latex command, killing the entire process tree on timeout."""
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        preexec_fn=os.setsid,  # new process group so all children can be killed together
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.communicate()
        raise


def _compile_with_engine(
    output_dir: Path, main_tex: Path, engine: TexEngine
) -> tuple[bool, str]:
    """Compile document with specified engine."""
    # Run latexmk from the project root so that sibling .sty files are found,
    # even when the main tex file lives in a subdirectory (e.g. acl/acl_latex.tex).
    compile_dir = output_dir
    tex_rel_path = str(main_tex.relative_to(output_dir))
    has_bib = bool(list(output_dir.glob("**/*.bib")))
    compile_cmd = get_compile_command(engine, tex_rel_path, use_bibtex=has_bib)
    max_attempts = 20
    installed_packages: set[str] = set()
    fixed_fonts: set[str] = set()
    last_output = ""

    for attempt in range(max_attempts):
        try:
            result = _run_latex(compile_cmd, compile_dir, timeout=300)
            pdf_path = compile_dir / (main_tex.stem + ".pdf")
            xdv_path = compile_dir / (main_tex.stem + ".xdv")

            # Check for missing BibTeX style files even when PDF was generated.
            # BibTeX errors only appear in .blg, not in latexmk stdout, so
            # latexmk may produce a PDF while all citations remain undefined.
            blg_path = compile_dir / (main_tex.stem + ".blg")
            missing_bst = parse_missing_bst_files(blg_path)
            new_bst = [pkg for pkg in missing_bst if pkg not in installed_packages]
            if new_bst and attempt < max_attempts - 1:
                print(f"  Missing BibTeX style packages: {', '.join(new_bst)}, installing...")
                if install_packages(new_bst):
                    installed_packages.update(new_bst)
                    print(f"  Retrying compilation (attempt {attempt + 2})...")
                    continue

            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                if result.returncode == 0:
                    print(f"✓ PDF generated: {pdf_path}")
                else:
                    print(f"✓ PDF generated (with warnings): {pdf_path}")
                subprocess.run(["open", str(output_dir)])
                return True, ""

            if (
                engine == TexEngine.XELATEX
                and xdv_path.exists()
                and xdv_path.stat().st_size > 0
            ):
                print("  Converting XDV to PDF...")
                try:
                    _run_latex(
                        ["xdvipdfmx", "-o", pdf_path.name, xdv_path.name],
                        compile_dir,
                        timeout=60,
                    )
                    if pdf_path.exists() and pdf_path.stat().st_size > 0:
                        if result.returncode == 0:
                            print(f"✓ PDF generated: {pdf_path}")
                        else:
                            print(f"✓ PDF generated (with warnings): {pdf_path}")
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

                if engine == TexEngine.PDFLATEX and re.search(
                    r"fontset\s*`.+?'\s*is unavailable in current", last_output
                ):
                    print("  CJK fontset incompatible with pdflatex, engine switch required")
                    return False, last_output

                if engine == TexEngine.PDFLATEX and re.search(
                    r"Font C70/[^=]+=\S+u[0-9a-f]{2} at .+ not loadable", last_output
                ):
                    print("  CJK subfont missing for non-CJK Unicode block, engine switch required")
                    return False, last_output

                if engine == TexEngine.PDFLATEX and attempt < max_attempts - 1:
                    missing_fonts = parse_missing_fonts(last_output)
                    new_fonts = [f for f in missing_fonts if f not in fixed_fonts]

                    if new_fonts:
                        print(f"  Detected missing fonts: {', '.join(new_fonts)}")
                        add_font_fallbacks_to_file(main_tex, new_fonts)
                        fixed_fonts.update(new_fonts)
                        print(f"  Added font fallbacks, retrying compilation...")
                        continue

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
    cfg: "TranslateConfig | None",
    metadata: dict | None,
    is_retry: bool = False,
) -> tuple[bool, str]:
    """Process paper with a specific engine."""
    if is_retry:
        print(f"\n{'='*50}")
        print(f"Retrying with {engine.value}...")
        print(f"{'='*50}")
        _reset_output_dir(paper_dir, output_dir)

    main_tex = None

    # Prefer the toplevel file declared in 00README.json over glob search,
    # because some source packages bundle engine-specific template files
    # (e.g. acl_lualatex.tex) that conflict with the CJK packages we inject.
    readme_path = output_dir / "00README.json"
    if readme_path.exists():
        try:
            readme = json.loads(readme_path.read_text())
            for source in readme.get("sources", []):
                if source.get("usage") == "toplevel":
                    candidate = output_dir / source["filename"]
                    if candidate.exists():
                        main_tex = candidate
                        break
        except Exception:
            pass

    if main_tex is None:
        tex_files = list(output_dir.glob("*.tex")) or list(output_dir.rglob("*.tex"))
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

    # If main tex lives in a subdirectory, BibTeX won't find .bst files there.
    # Copy them to output_dir so bibtex can locate them.
    main_tex_dir = main_tex.parent
    if main_tex_dir != output_dir:
        for bst_file in main_tex_dir.glob("*.bst"):
            dest = output_dir / bst_file.name
            if not dest.exists():
                shutil.copy2(bst_file, dest)

    english_only = cfg and cfg.english_only_mode

    if not english_only:
        visited: set[Path] = set()
        included_files = find_included_files(main_tex, output_dir, visited)

        from papercli.translate.latex.parser import FileParseResult

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

        max_workers = cfg.max_workers if cfg else 10
        translations = batch_translate(all_tasks, output_dir, max_workers)

        print("Assembling translated files...")
        for file_path, parse_result in file_results.items():
            final_content = assemble_translated_file(parse_result, translations)
            file_path.write_text(final_content, encoding="utf-8")

        if cfg and cfg.toc:
            print("Adding List of Tables/Figures and Table of Contents...")
            main_content = main_tex.read_text(encoding="utf-8")
            main_content = add_toc(main_content)
            main_content = add_lot_lof(main_content)
            main_tex.write_text(main_content, encoding="utf-8")

        print(f"Adding CJK support to {main_tex.name} ({engine.value})...")
        main_content = main_tex.read_text(encoding="utf-8")
        fonts = cfg.fonts if cfg else None
        main_content = add_cjk_support(
            main_content,
            engine=engine,
            arxiv_id=metadata.get("arxiv_id") if metadata else None,
            published_date=metadata.get("published") if metadata else None,
            category=metadata.get("category") if metadata else None,
            trans_gray=cfg.trans_gray if cfg else 0.4,
            trans_fontsize=cfg.trans_fontsize if cfg else "",
            font_xelatex=fonts.xelatex if fonts else "PingFang SC",
            font_lualatex=fonts.lualatex if fonts else "PingFang SC",
            font_pdflatex=fonts.pdflatex if fonts else "gbsn",
        )
        main_tex.write_text(main_content, encoding="utf-8")

    print(f"\nCompiling with {engine.value}...")
    return _compile_with_engine(output_dir, main_tex, engine)


def process_paper(paper_dir: Path) -> None:
    """Process a paper directory and generate bilingual PDF."""
    cfg = get_config()
    print(f"Processing: {paper_dir.name}")

    suffix = "_compiled" if (cfg and cfg.english_only_mode) else "_bilingual"
    output_dir = paper_dir.parent / f"{paper_dir.name}{suffix}"

    if cfg and cfg.resume and output_dir.exists():
        cache_dir = output_dir / ".translations"
        cached_count = 0
        if cache_dir.exists():
            cached_count = len(list(cache_dir.glob("*.txt")))
        _reset_output_dir(paper_dir, output_dir)
        print(f"Resuming translation in {output_dir}")
        if cached_count > 0:
            print(f"  Found {cached_count} cached translations")
    else:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        shutil.copytree(paper_dir, output_dir)
        print(f"Copied to: {output_dir}")

    detected_engine = detect_engine(output_dir)
    if detected_engine == TexEngine.PDFLATEX:
        color = "\033[1;33m"
        hint = "pdfLaTeX features detected (fontenc, inputenc, etc.)"
    elif detected_engine == TexEngine.LUALATEX:
        color = "\033[1;35m"
        hint = "LuaLaTeX features detected (luatexja, directlua, etc.)"
    else:
        color = "\033[1;36m"
        hint = "XeLaTeX compatible (default)"
    print(f"Source analysis: {color}[{detected_engine.value}]\033[0m - {hint}")

    engine_mode = cfg.engine if cfg else ""
    if engine_mode == "xelatex":
        engine = TexEngine.XELATEX
        print(f"Engine: \033[1;32m[xelatex]\033[0m (user specified)")
    elif engine_mode == "pdflatex":
        engine = TexEngine.PDFLATEX
        print(f"Engine: \033[1;32m[pdflatex]\033[0m (user specified)")
    elif engine_mode == "lualatex":
        engine = TexEngine.LUALATEX
        print(f"Engine: \033[1;32m[lualatex]\033[0m (user specified)")
    else:
        engine = detected_engine
        print(f"Engine: \033[1;32m[{engine.value}]\033[0m (detected from document)")

    arxiv_id = extract_arxiv_id_from_path(paper_dir)
    metadata = None
    if arxiv_id:
        print(f"Fetching arXiv metadata for {arxiv_id}...")
        metadata = get_arxiv_metadata(arxiv_id)
        if metadata:
            print(f"  Published: {metadata['published']}")
            if metadata.get("category"):
                print(f"  Category: {metadata['category']}")

    success, error_output = _process_with_engine(
        paper_dir, output_dir, engine, cfg, metadata, is_retry=False
    )

    if not success:
        print(f"\n\033[1;31m[Compilation failed ({engine.value})]\033[0m")
        if error_output == "latexmk not found":
            print("Error: latexmk not found. Please install TinyTeX or BasicTeX:")
            print("  TinyTeX: curl -sL 'https://yihui.org/tinytex/install-bin-unix.sh' | sh")
            print("  BasicTeX: brew install --cask basictex")
        elif engine == TexEngine.PDFLATEX and re.search(
            r"Font C70/[^=]+=\S+u[0-9a-f]{2} at .+ not loadable"
            r"|fontset\s*`.+?'\s*is unavailable in current",
            error_output,
        ):
            print("CJK fonts are not supported by pdflatex.")
            print("Hint: re-run with --engine xelatex")
        else:
            print(error_output[-2000:] if len(error_output) > 2000 else error_output)

    print(f"\nOutput directory: {output_dir}")
