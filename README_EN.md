# LaTeX Paper Translation Tool

[中文](README.md) | English

Translate arXiv paper LaTeX source files into bilingual Chinese-English PDFs.

## Features

- **arXiv Auto Download**: Supports arXiv ID or URL, automatically downloads source files
- **Smart File Parsing**: Recursively parses `\input{}` and `\include{}`, automatically discovers all files that need translation
- **Selective Translation**: Skips preamble/config files, only translates body content
- **Preserve Original**: Translation displayed in gray small font below original text for easy comparison
- **Auto Fix Conflicts**: Handles common LaTeX package conflicts (subfigure/subcaption, natbib, CJK, etc.)
- **XeTeX Compilation**: Uses tectonic for compilation, auto downloads required packages, native Chinese support

## Installation

### System Dependencies

```bash
# macOS
brew install tectonic
```

### Python Dependencies

```bash
pip install requests tqdm draccus
```

### Environment Variables

```bash
# Translation API Key (required, unless using --model x test mode)
export ONE_API="your-api-key"

# Custom API endpoint (optional, default https://api.bltcy.ai/v1/chat/completions)
export API_URL="https://your-api-endpoint/v1/chat/completions"
```

## Usage

```bash
# arXiv ID (auto downloads latest version)
python translate.py --input 2307.16789

# Specific version
python translate.py --input 2307.16789v1

# arXiv URL (supports abs/pdf/src/html)
python translate.py --input https://arxiv.org/abs/2307.16789
python translate.py --input https://arxiv.org/pdf/2307.16789

# Local archive
python translate.py --input tex/arXiv-2307.16789.tar.gz

# Local directory
python translate.py --input tex/arXiv-2307.16789v2

# Debug mode (no API calls, uses mock translation)
python translate.py --input 2307.16789 --model x

# Custom model
python translate.py --input 2307.16789 --model gpt-4.1-mini

# Resume translation (continue after interruption, reuse cache)
python translate.py --input 2307.16789 --resume true

# Adjust concurrency (default 10)
python translate.py --input 2307.16789 --max_workers 20

# Show help
python translate.py --help
```

## Input Formats

| Format | Example | Description |
|--------|---------|-------------|
| arXiv ID | `2307.16789` | Downloads latest version |
| With version | `2307.16789v2` | Downloads specific version |
| abs URL | `https://arxiv.org/abs/2307.16789` | Extracts ID from abs page |
| pdf URL | `https://arxiv.org/pdf/2307.16789` | Extracts ID from pdf link |
| src URL | `https://arxiv.org/src/2307.16789` | Extracts ID from source link |
| Local directory | `tex/arXiv-xxx` | Processes local directory directly |
| Archive | `tex/arXiv-xxx.tar.gz` | Extracts first then processes |

## Output Structure

```
tex/
├── arXiv-2307.16789v2.tar.gz      # Downloaded source files
├── arXiv-2307.16789v2/            # Extracted original files
└── arXiv-2307.16789v2_bilingual/  # Translation output
    ├── .translations/             # Translation cache (for resume)
    │   ├── a1b2c3d4e5f6.txt       # Paragraph hash → translation
    │   └── ...
    ├── main.tex                   # LaTeX with translations added
    ├── sections/*.tex             # Translated section files
    └── main.pdf                   # Final bilingual PDF
```

## Workflow

```
Input (ID/URL/directory/archive)
    ↓
[arXiv download] → tex/arXiv-{id}.tar.gz
    ↓
[Extract] → tex/arXiv-{id}/
    ↓
[Copy] → tex/arXiv-{id}_bilingual/
    ↓
[Fix package conflicts] subfigure/subcaption, natbib, CJK
    ↓
[Add Chinese support] xeCJK, fontspec, \trans{} command
    ↓
[Parse files] Recursively find \input{} and \include{} from main file
    ↓
[Global parallel translation] Three-phase processing (see below)
    ↓
[Compile] tectonic → PDF
    ↓
[Open] Automatically open generated PDF
```

### Global Parallel Translation Architecture

Uses a "global parallel" strategy where all paragraphs from all files are translated concurrently:

```
Phase 1: Parse
├── Parse main.tex
├── Parse section1.tex
├── Parse section2.tex
└── Collect all paragraph tasks → [task_0, task_1, ..., task_83]

Phase 2: Translate
└── batch_translate([all paragraphs]) → One-time concurrent (limited by max_workers)

Phase 3: Assemble
├── Distribute translation results back to main.tex
├── Distribute translation results back to section1.tex
└── Distribute translation results back to section2.tex
```

Advantages:
- **Faster**: 7 files only need 1 network round-trip, not 7
- **More efficient**: All paragraphs uniformly scheduled, not blocked by slow paragraphs in single file
- **Resume-friendly**: Cache based on paragraph content hash, independent of file structure

## Translation Rules

### Content Translated
- Body paragraphs (separated by blank lines)
- Content after section headings
- Figure/table captions `\caption{...}`
- itemize/enumerate list items

### Content Skipped
- Preamble (before `\begin{document}`)
- Math environments (equation, align, gather)
- Code blocks (lstlisting, verbatim)
- Table content (tabular)
- Algorithm environments (algorithm)
- Config files (config.tex, macro.tex, etc.)
- Pure LaTeX command lines

### Preserved Without Translation
- Inline math `$...$`
- Citations `\cite{}`, `\ref{}`
- LaTeX command structure

## Auto-Fixed Issues

| Issue | Solution |
|-------|----------|
| subfigure/subcaption conflict | Comment out subfigure (keep subcaption) |
| natbib + unsrt incompatible | Add `[numbers]` option |
| CJK/CJKutf8 conflicts with xeCJK | Comment out old packages, remove CJK environment |
| hyperref pdftex driver error | Add `\PassOptionsToPackage{xetex}{hyperref}` |
| Fonts don't support XeTeX | Use fontspec to set system fonts |

## Command Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--input` | (required) | Input source: arXiv ID, URL, local directory or archive |
| `--model` | `gpt-5-nano` | Translation model, use `x` for test mode |
| `--max_workers` | `10` | Maximum concurrent API requests |
| `--resume` | `false` | Resume translation, reuse cached translations |
| `--help` | - | Show help message |

### Model Options

- `gpt-5-nano` - Default model
- `gpt-4.1-mini` - More powerful model
- `x` / `debug` / `none` - Test mode, no API calls, uses mock translation

### Resume Translation

If translation is interrupted (network error, API rate limit, etc.), use `--resume true` to continue:

```bash
# First translation (interrupted midway)
python translate.py --input 2307.16789

# Continue translation (reuse completed translations)
python translate.py --input 2307.16789 --resume true
```

Cache mechanism:
- Each paragraph is saved to `.translations/` immediately after translation
- Matches based on paragraph content hash, reusable even if file structure changes
- Output example: `Cached: 58, Pending: 6` (58 cached, 6 pending)

### Concurrency Control

Adjust concurrency based on API rate limits:

```bash
# Lower concurrency (when API rate limiting is strict)
python translate.py --input 2307.16789 --max_workers 5

# Higher concurrency (when API rate limiting is relaxed)
python translate.py --input 2307.16789 --max_workers 20
```

## File Description

```
translation/
├── translate.py    # Main program
├── bugs.md         # Bug records and fix history
├── README.md       # Chinese documentation
├── README_EN.md    # This document (English)
└── tex/            # Paper directory (auto created)
```

## FAQ

### Q: What to do if compilation fails?
Check tectonic error output, common causes:
- Missing fonts: Ensure system has Times New Roman, STHeiti
- Package conflicts: Check for unhandled package conflicts
- Syntax errors: Translation may have introduced special characters

### Q: How to skip certain files?
Add filename patterns in the `is_preamble_file()` function.

### Q: How to change translation API?
Set environment variable `API_URL`, must be compatible with OpenAI API format.

### Q: Where are downloaded files saved?
All files are saved in `tex/` directory, including:
- `arXiv-{id}.tar.gz` - Original archive
- `arXiv-{id}/` - Extracted source files
- `arXiv-{id}_bilingual/` - Translation output

## Example Output

Translated LaTeX format:

```latex
Large Language Models (LLMs) have emerged as a pivotal
breakthrough in natural language processing (NLP).

\trans{大型语言模型（LLMs）已成为自然语言处理（NLP）领域的重要突破。}

\begin{figure}
    \caption{Overview of our approach.}
    \trans{我们方法的概览。}
\end{figure}
```

PDF display: Original text in normal black, translation in gray small font.
