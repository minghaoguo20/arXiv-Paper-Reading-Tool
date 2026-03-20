#!/usr/bin/env python3
"""
LaTeX Paper Translator - Translates LaTeX papers to bilingual PDF via tectonic.

Usage:
    python translate.py <paper_path>

Examples:
    python translate.py tex/arXiv-2511.05271v4
    python translate.py tex/arXiv-2402.01030v4.tar.gz

Supports:
    - Directory with LaTeX source files
    - .tar.gz archive (auto-extracts)

Environment:
    ONE_API - API key for bltcy.ai (for real translation)

Output:
    Creates <paper_name>_bilingual/ directory with translated PDF
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import requests
from tqdm import tqdm

# Translation API configuration (from /translate skill)
API_URL = "https://api.bltcy.ai/v1/chat/completions"
MODEL_NAME = "gpt-4.1-nano"

# Test mode flag
TEST_MODE = True


def translate(text: str, target_lang: str = "Chinese", max_retries: int = 3) -> str:
    """Translate text using bltcy.ai API with retry."""
    if not text.strip():
        return ""

    if TEST_MODE:
        # Return mock translation for testing (pure Chinese, no special chars)
        clean = re.sub(r'\\[a-zA-Z]+(\{[^}]*\}|\[[^\]]*\])*', '', text)
        clean = re.sub(r'[{}\[\]$%&#_^~\\]', '', clean)  # Remove special chars
        clean = re.sub(r'\s+', ' ', clean).strip()
        words = clean.split()[:15]
        truncated = ' '.join(words)
        return f"（测试翻译）{truncated}……"

    api_key = os.environ.get("ONE_API")
    if not api_key:
        raise ValueError("ONE_API environment variable is required")

    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    f"You are a professional translator specializing in academic papers. "
                    f"Translate the following English text to {target_lang}. "
                    "Keep all LaTeX commands, math formulas, and citations intact. "
                    "Only output the translation, nothing else."
                )
            },
            {"role": "user", "content": text}
        ]
    }

    import time
    for attempt in range(max_retries):
        try:
            response = requests.post(API_URL, headers=headers, data=json.dumps(payload), timeout=60)
            result = response.json()
            if 'choices' in result:
                return result['choices'][0]['message']['content']
            elif 'error' in result:
                print(f"API error: {result['error']}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
            return text  # Return original on failure
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return text
    return text


def add_cjk_support(main_tex_content: str) -> str:
    """Add xeCJK package to main tex file for Chinese support."""
    # First, add hyperref xetex driver option after \documentclass (before hyperref is loaded)
    doc_class_match = re.search(r'(\\documentclass[^\n]*\n)', main_tex_content)
    if doc_class_match:
        # Add xetex option for hyperref before any package loading
        hyperref_fix = r"""
% === XeTeX compatibility (auto-added) ===
\PassOptionsToPackage{xetex}{hyperref}
\PassOptionsToPackage{xetex}{graphicx}
"""
        insert_pos = doc_class_match.end()
        main_tex_content = main_tex_content[:insert_pos] + hyperref_fix + main_tex_content[insert_pos:]

    # Insert xeCJK and fontspec BEFORE \begin{document} to override any font settings
    doc_begin_match = re.search(r'(\\begin\{document\})', main_tex_content)
    if doc_begin_match:
        cjk_config = r"""
% === Chinese Support (auto-added by translator) ===
\usepackage{fontspec}
\usepackage{xeCJK}
\setCJKmainfont{STHeiti}
% Override Times font (ptm) with native Times New Roman
\setmainfont{Times New Roman}[Ligatures=TeX]
\setsansfont{Helvetica}
\setmonofont{Courier New}
% Translation style
\definecolor{transcolor}{gray}{0.4}
\newcommand{\trans}[1]{{\small\color{transcolor}#1}}
% === End Chinese Support ===

"""
        insert_pos = doc_begin_match.start()
        main_tex_content = main_tex_content[:insert_pos] + cjk_config + main_tex_content[insert_pos:]

    return main_tex_content


def is_translatable_paragraph(text: str) -> bool:
    """Check if a text block should be translated."""
    text = text.strip()
    if len(text) < 30:
        return False
    # Skip if mostly LaTeX commands
    if text.count('\\') > len(text) / 10:
        return False
    # Skip if it's a single command
    if re.match(r'^\\[a-zA-Z]+(\{[^}]*\}|\[[^\]]*\])*$', text):
        return False
    return True


def clean_for_translation(text: str) -> str:
    """Clean LaTeX text before translation, removing commands but keeping content."""
    # Remove comments
    text = re.sub(r'%.*', '', text)
    # Remove \begin{...}[options] and \end{...}
    text = re.sub(r'\\begin\{[^}]+\}(\[[^\]]*\])?', '', text)
    text = re.sub(r'\\end\{[^}]+\}', '', text)
    # Remove \item with optional label
    text = re.sub(r'\\item(\[[^\]]*\])?', '', text)
    # Remove \label{...}
    text = re.sub(r'\\label\{[^}]*\}', '', text)
    # Simplify formatting commands but keep content
    text = re.sub(r'\\textit\{([^{}]*)\}', r'\1', text)
    text = re.sub(r'\\textbf\{([^{}]*)\}', r'\1', text)
    text = re.sub(r'\\emph\{([^{}]*)\}', r'\1', text)
    # Keep citations as [cite]
    text = re.sub(r'~?\\cite[pt]?\{[^}]*\}', '[cite]', text)
    text = re.sub(r'~?\\ref\{[^}]*\}', '[ref]', text)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def escape_for_latex(text: str) -> str:
    """Escape special characters in translated text for LaTeX."""
    # Remove any remaining LaTeX commands (they shouldn't be in translation)
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    # Remove braces (they're LaTeX-specific)
    text = text.replace('{', '').replace('}', '')
    # Escape special LaTeX characters
    text = text.replace('\\', '')  # Remove backslashes
    text = text.replace('$', r'\$')
    text = text.replace('%', r'\%')
    text = text.replace('&', r'\&')
    text = text.replace('#', r'\#')
    text = text.replace('_', r'\_')
    text = text.replace('^', '')
    text = text.replace('~', ' ')
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_caption_content(text: str) -> str:
    """Extract content from \caption{...} handling nested braces."""
    match = re.search(r'\\caption\{', text)
    if not match:
        return ""
    start = match.end()
    depth = 1
    end = start
    while end < len(text) and depth > 0:
        if text[end] == '{':
            depth += 1
        elif text[end] == '}':
            depth -= 1
        end += 1
    return text[start:end-1]


def translate_caption_line(line: str) -> str:
    """If line contains \caption, add translation after it."""
    if '\\caption{' not in line:
        return line

    caption_content = extract_caption_content(line)
    if not caption_content or len(caption_content) < 10:
        return line

    # Clean and translate caption
    clean_caption = clean_for_translation(caption_content)
    if len(clean_caption) < 10:
        return line

    translated = translate(clean_caption)
    escaped = escape_for_latex(translated)

    # Add translation after the caption line
    return line + '\n    \\trans{' + escaped + '}'


def translate_section_file(content: str, is_main_file: bool = False) -> str:
    """Translate a section file, adding Chinese translation after each paragraph."""
    result_lines = []
    lines = content.split('\n')

    # Track environments - separate caption-able envs from others
    caption_envs = ['figure', 'table']
    skip_envs = ['equation', 'align', 'gather', 'lstlisting',
                 'algorithm', 'tabular', 'minipage', 'adjustbox', 'center', 'tcolorbox']
    all_envs = caption_envs + skip_envs
    env_depth = {env: 0 for env in all_envs}

    current_para = []
    in_document = not is_main_file  # If main file, wait for \begin{document}

    def in_any_skip_env():
        return any(env_depth[env] > 0 for env in all_envs)

    def in_caption_env():
        return any(env_depth[env] > 0 for env in caption_envs)

    def flush_paragraph():
        """Process accumulated paragraph."""
        nonlocal current_para
        if not current_para:
            return

        para_text = '\n'.join(current_para)
        result_lines.extend(current_para)

        # Check if paragraph should be translated
        clean_para = clean_for_translation(para_text)
        if is_translatable_paragraph(clean_para):
            translated = translate(clean_para)
            escaped = escape_for_latex(translated)
            # Add translation as a new paragraph in gray
            result_lines.append('')
            result_lines.append(r'\trans{' + escaped + '}')
            result_lines.append('')

        current_para = []

    for line in lines:
        stripped = line.strip()

        # Track \begin{document} and \end{document}
        if r'\begin{document}' in stripped:
            in_document = True
            result_lines.append(line)
            continue
        if r'\end{document}' in stripped:
            flush_paragraph()
            in_document = False
            result_lines.append(line)
            continue

        # If not in document body (preamble), just copy line
        if not in_document:
            result_lines.append(line)
            continue

        # Track environment depth
        for env in all_envs:
            if re.search(r'\\begin\{' + env + r'\*?\}', stripped):
                env_depth[env] += 1
            if re.search(r'\\end\{' + env + r'\*?\}', stripped):
                env_depth[env] = max(0, env_depth[env] - 1)

        # If in skip environment, handle specially
        if in_any_skip_env():
            flush_paragraph()
            # Translate captions in figure/table environments
            if in_caption_env() and '\\caption{' in line:
                result_lines.append(translate_caption_line(line))
            else:
                result_lines.append(line)
            continue

        # Check for section headers
        if re.match(r'\\(section|subsection|subsubsection)\{', stripped):
            flush_paragraph()
            result_lines.append(line)
            continue

        # Empty line = paragraph break
        if not stripped:
            flush_paragraph()
            result_lines.append(line)
            continue

        # Comment line
        if stripped.startswith('%'):
            flush_paragraph()
            result_lines.append(line)
            continue

        # Accumulate paragraph
        current_para.append(line)

    flush_paragraph()

    return '\n'.join(result_lines)


def fix_package_conflicts(output_dir: Path) -> None:
    """Fix common LaTeX package conflicts across the entire project."""
    # Collect all tex content to detect project-wide conflicts
    all_tex_files = list(output_dir.glob("**/*.tex"))
    all_content = ""
    for tex_file in all_tex_files:
        try:
            all_content += tex_file.read_text(encoding='utf-8')
        except:
            continue

    # Check for subfigure/subcaption conflict project-wide
    has_subfigure = r'\usepackage{subfigure}' in all_content
    has_subcaption = r'\usepackage{subcaption}' in all_content

    if has_subfigure and has_subcaption:
        # Comment out all subfigure uses (subcaption is newer and preferred)
        for tex_file in all_tex_files:
            try:
                content = tex_file.read_text(encoding='utf-8')
                if r'\usepackage{subfigure}' in content:
                    content = content.replace(
                        r'\usepackage{subfigure}',
                        r'%\usepackage{subfigure} % commented: conflicts with subcaption'
                    )
                    tex_file.write_text(content, encoding='utf-8')
                    print(f"  Fixed subfigure/subcaption conflict in {tex_file.name}")
            except:
                continue

    # Fix natbib with unsrt/plain bibliographystyle (needs numbers option)
    for tex_file in all_tex_files:
        try:
            content = tex_file.read_text(encoding='utf-8')
            # If using natbib without options and numeric bibliographystyle
            if r'\usepackage{natbib}' in content:
                if re.search(r'\\bibliographystyle\{(unsrt|plain|abbrv|ieeetr|acm)\}', content):
                    content = content.replace(
                        r'\usepackage{natbib}',
                        r'\usepackage[numbers]{natbib}'
                    )
                    tex_file.write_text(content, encoding='utf-8')
                    print(f"  Fixed natbib citation style in {tex_file.name}")
        except:
            continue

    # Replace old CJK package with xeCJK (for XeTeX compatibility)
    # Check for any CJK-related packages
    has_cjk = re.search(r'\\usepackage\{CJK(utf8)?\}', all_content)
    if has_cjk:
        for tex_file in all_tex_files:
            try:
                content = tex_file.read_text(encoding='utf-8', errors='replace')
                original = content
                # Comment out old CJK packages (CJK, CJKutf8)
                content = re.sub(
                    r'\\usepackage\{CJK(utf8)?\}',
                    r'%\\usepackage{CJK} % replaced by xeCJK',
                    content
                )
                # Replace \begin{CJK} and \begin{CJK*} variants with empty
                content = re.sub(r'\\begin\{CJK\*?\}\{[^}]*\}\{[^}]*\}', '', content)
                content = re.sub(r'\\end\{CJK\*?\}', '', content)
                if content != original:
                    tex_file.write_text(content, encoding='utf-8')
                    print(f"  Fixed CJK usage in {tex_file.name}")
            except:
                continue


def process_paper(paper_dir: Path) -> None:
    """Process a paper directory and generate bilingual PDF."""
    print(f"Processing: {paper_dir.name}")

    # Create output directory with copy of paper
    output_dir = paper_dir.parent / f"{paper_dir.name}_bilingual"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(paper_dir, output_dir)
    print(f"Copied to: {output_dir}")

    # Fix common package conflicts
    print("Checking for package conflicts...")
    fix_package_conflicts(output_dir)

    # Find main tex file (must contain \documentclass)
    main_tex = None
    tex_files = list(output_dir.glob("*.tex"))
    for tex_file in tex_files:
        try:
            content = tex_file.read_text(encoding='utf-8')
            if r'\documentclass' in content:
                main_tex = tex_file
                break
        except:
            continue
    if main_tex is None:
        raise FileNotFoundError("No main tex file found (no file with \\documentclass)")

    # Add CJK support to main file
    print(f"Adding CJK support to {main_tex.name}...")
    main_content = main_tex.read_text(encoding='utf-8')
    main_content = add_cjk_support(main_content)
    main_tex.write_text(main_content, encoding='utf-8')

    # Find all included files by parsing \input{} and \include{}
    def is_preamble_file(filepath: Path) -> bool:
        """Check if a file is a preamble/config file (should not be translated)."""
        name = filepath.stem.lower()
        # Skip by filename
        if any(skip in name for skip in ['config', 'preamble', 'header', 'macro', 'command', 'setup']):
            return True
        # Check content - if mostly \usepackage/\def/\newcommand, it's preamble
        try:
            content = filepath.read_text(encoding='utf-8', errors='replace')
            lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith('%')]
            if not lines:
                return True
            preamble_cmds = sum(1 for l in lines if re.match(r'\\(usepackage|RequirePackage|def|newcommand|renewcommand|setlength|definecolor)', l))
            # If more than 50% are preamble commands, skip
            if preamble_cmds / len(lines) > 0.5:
                return True
        except:
            pass
        return False

    def find_included_files(tex_file: Path, base_dir: Path, visited: set) -> list[Path]:
        """Recursively find all files included via \input or \include."""
        if tex_file in visited or not tex_file.exists():
            return []
        visited.add(tex_file)

        included = []
        try:
            content = tex_file.read_text(encoding='utf-8', errors='replace')
            # Find \input{...} and \include{...}
            patterns = [
                r'\\input\{([^}]+)\}',
                r'\\include\{([^}]+)\}'
            ]
            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    ref = match.group(1).strip()
                    # Skip common non-translatable includes
                    if any(skip in ref.lower() for skip in ['table', 'bib', 'sty', 'cls', 'bbl', 'fig']):
                        continue
                    # Add .tex extension if missing
                    if not ref.endswith('.tex'):
                        ref += '.tex'
                    # Resolve path relative to base_dir
                    inc_path = base_dir / ref
                    if inc_path.exists() and inc_path not in visited:
                        # Skip preamble/config files
                        if is_preamble_file(inc_path):
                            continue
                        included.append(inc_path)
                        # Recursively find includes in this file
                        included.extend(find_included_files(inc_path, base_dir, visited))
        except:
            pass
        return included

    # Start from main file and find all included files
    visited = set()
    included_files = find_included_files(main_tex, output_dir, visited)

    # Always translate main file (document body)
    print(f"Translating main file: {main_tex.name}")
    content = main_tex.read_text(encoding='utf-8', errors='replace')
    translated_content = translate_section_file(content, is_main_file=True)
    main_tex.write_text(translated_content, encoding='utf-8')

    # Also translate included files
    if included_files:
        print(f"Translating {len(included_files)} included files")
        for inc_file in tqdm(included_files, desc="Translating"):
            rel_path = inc_file.relative_to(output_dir)
            print(f"  {rel_path}")
            content = inc_file.read_text(encoding='utf-8', errors='replace')
            translated_content = translate_section_file(content)
            inc_file.write_text(translated_content, encoding='utf-8')

    # Compile with tectonic
    print("\nCompiling with tectonic...")
    try:
        result = subprocess.run(
            ['tectonic', main_tex.name],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            pdf_name = main_tex.stem + '.pdf'
            print(f"✓ PDF generated: {output_dir / pdf_name}")
            # Open PDF
            subprocess.run(['open', output_dir / pdf_name])
        else:
            print(f"Tectonic failed:")
            print(result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)
    except subprocess.TimeoutExpired:
        print("Tectonic compilation timed out")
    except Exception as e:
        print(f"Compilation error: {e}")

    print(f"\nOutput directory: {output_dir}")


def extract_archive(archive_path: Path) -> Path:
    """Extract tar.gz archive and return the extracted directory."""
    import tarfile

    extract_dir = archive_path.parent

    # Determine the folder name (remove .tar.gz or .tgz)
    name = archive_path.name
    if name.endswith('.tar.gz'):
        folder_name = name[:-7]
    elif name.endswith('.tgz'):
        folder_name = name[:-4]
    else:
        folder_name = name

    target_dir = extract_dir / folder_name

    # Extract if not already extracted
    if not target_dir.exists():
        print(f"Extracting {archive_path.name}...")
        with tarfile.open(archive_path, 'r:gz') as tar:
            # Check if archive has a top-level directory
            members = tar.getnames()
            has_top_dir = all(m.startswith(members[0].split('/')[0] + '/') or m == members[0].split('/')[0]
                             for m in members) if members else False

            if has_top_dir:
                # Extract directly, top-level dir exists
                tar.extractall(path=extract_dir)
            else:
                # Create target dir and extract into it
                target_dir.mkdir(parents=True, exist_ok=True)
                tar.extractall(path=target_dir)
        print(f"Extracted to: {target_dir}")
    else:
        print(f"Already extracted: {target_dir}")

    return target_dir


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_path = Path(sys.argv[1])

    # Handle relative paths
    if not input_path.is_absolute():
        input_path = Path.cwd() / input_path

    # Check if it's an archive
    if input_path.suffix == '.gz' or input_path.name.endswith('.tar.gz') or input_path.suffix == '.tgz':
        if not input_path.exists():
            print(f"Error: Archive not found: {input_path}")
            sys.exit(1)
        paper_dir = extract_archive(input_path)
    else:
        paper_dir = input_path

    if not paper_dir.exists():
        print(f"Error: Paper directory not found: {paper_dir}")
        sys.exit(1)

    if not paper_dir.is_dir():
        print(f"Error: Not a directory: {paper_dir}")
        sys.exit(1)

    process_paper(paper_dir)


if __name__ == "__main__":
    main()
