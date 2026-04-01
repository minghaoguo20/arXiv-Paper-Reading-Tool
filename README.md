# arXiv Paper Translation Tool

[English](README.md) | [中文](README-zh.md)

Translate arXiv paper into bilingual PDFs.

## Features

- **arXiv Auto-Download**: Supports arXiv ID or URL, automatically downloads source files
- **Smart File Parsing**: Recursively parses `\input{}` and `\include{}`, automatically discovers all files that need translation
- **Selective Translation**: Skips preamble/config files, only translates main content
- **Original Text Preserved**: Translation appears in small gray text below the original for easy comparison
- **Auto-Conflict Resolution**: Handles common LaTeX package conflicts (subfigure/subcaption, natbib, CJK, etc.)
- **Smart Engine Selection**: Uses XeLaTeX by default (better CJK support), with interactive fallback to pdfLaTeX on failure
- **Auto-Install Missing Packages**: Automatically detects and installs missing LaTeX packages during compilation
- **arXiv Metadata Watermark**: Automatically fetches arXiv paper publication date and categories, adds to PDF top-right corner
- **Table of Contents Generation**: Optional addition of TOC, List of Tables (LOT), and List of Figures (LOF)
- **Resume Translation**: Supports resuming interrupted translations, reusing cached results

## Important Notes

**Compatibility Limitations**: Due to the diverse LaTeX formats used in arXiv papers, this tool cannot guarantee:
- All papers will successfully translate and compile
- Post-translation formatting will perfectly match expectations
- Complete handling of special content (complex math environments, custom macros, etc.)

**Actual Results**: For most papers in standard formats, translation quality is sufficient for reading without significant issues.

**Issue Reporting**: When encountering papers that cannot be processed, please submit an Issue with the arXiv link to help us continuously improve.

## Quick Start

> **Note**: This project has only been tested on macOS. Linux systems should theoretically be compatible. Windows users may need to adjust some installation steps.

### Installation

#### 1. Python Dependencies

```bash
pip install -r requirements.txt
```

#### 2. LaTeX Compiler

We recommend using TinyTeX (lightweight LaTeX distribution):

```bash
# Install TinyTeX
curl -sL "https://yihui.org/tinytex/install-bin-unix.sh" | sh

# Install basic CJK support packages
tlmgr install cjk ctex xecjk fontspec
```

> **Note**: Missing packages will be automatically installed during compilation, no manual intervention needed.

#### 3. Environment Variables

Two configuration methods are supported:

**Method 1: Using .env file (Recommended)**

```bash
# Copy template file
cp .env.example .env

# Edit .env file and fill in your API Key
# ONE_API=your-api-key-here
# API_URL=https://api.openai.com/v1/chat/completions
```

**Method 2: Direct environment variable export**

```bash
# Translation API Key (required, unless using test mode)
export ONE_API="your-api-key"

# Custom API address (optional)
export API_URL="https://api.openai.com/v1/chat/completions"
```

> **Note**:
> - `ONE_API`: Translation API key, obtained from service provider
> - `API_URL`: API endpoint address, must be OpenAI-compatible (optional, has default value)
> - Choose either configuration method, `.env` file is more convenient for management

### Basic Usage

```bash
# Download and translate from arXiv
python translate.py --input 2307.16789
python translate.py --input 2307.16789v2
python translate.py --input https://arxiv.org/abs/2307.16789

# Specify local directory
python translate.py --input tex/arXiv-2511.05271v4
python translate.py --input tex/paper.tar.gz
```

### Configuration Files

**Available configuration files:**

- `translator/config/default.yaml` - Default configuration template (detailed comments)

**Parameter priority:**

Command-line arguments > Configuration file > Default values

```bash
# CLI arguments override config file settings
python translate.py --config_path translator/config/default.yaml --input 2307.16789 --model gpt-4.1-mini --target_lang Japanese

# Use default config file and directly specify target language
python translate.py --input 2307.16789 --target_lang Korean

# Custom config file (copy default.yaml and modify)
cp translator/config/default.yaml my_config.yaml
python translate.py --config_path my_config.yaml --input 2307.16789
```

## Common Options

### Default Mode

```bash
python translate.py --input 2307.16789
```

### Test Mode (No API calls)

```bash
python translate.py --input 2307.16789 --model x
```

### Custom Translation Model

```bash
python translate.py --input 2307.16789 --model gpt-4.1-mini
```

### Resume Translation

```bash
# Initial translation (interrupted midway)
python translate.py --input 2307.16789

# Continue translation (reuse cache)
python translate.py --input 2307.16789 --resume true
```

### Adjust Concurrency

```bash
# Reduce concurrency (strict API rate limiting)
python translate.py --input 2307.16789 --max_workers 10

# Increase concurrency (default 30)
python translate.py --input 2307.16789 --max_workers 50
```

### Specify LaTeX Engine

```bash
# Auto-select (default): XeLaTeX first, optional pdfLaTeX on failure
python translate.py --input 2307.16789 --engine auto

# Force XeLaTeX
python translate.py --input 2307.16789 --engine xelatex

# Force pdfLaTeX
python translate.py --input 2307.16789 --engine pdflatex
```

### Table of Contents and Lists

```bash
# Add TOC and figure/table lists (enabled by default)
python translate.py --input 2307.16789 --toc true

# Don't add TOC
python translate.py --input 2307.16789 --toc false
```

## Input Formats

| Format | Example | Description |
|--------|---------|-------------|
| arXiv ID | `2307.16789` | Download latest version |
| With version | `2307.16789v2` | Download specific version |
| abs URL | `https://arxiv.org/abs/2307.16789` | Extract ID from abstract page |
| pdf URL | `https://arxiv.org/pdf/2307.16789` | Extract ID from PDF link |
| src URL | `https://arxiv.org/src/2307.16789` | Extract ID from source link |
| Local directory | `tex/arXiv-xxx` | Process local directory directly |
| Archive | `tex/arXiv-xxx.tar.gz` | Extract then process |

## Output Structure

```
tex/
├── arXiv-2307.16789v2.tar.gz      # Downloaded source file
├── arXiv-2307.16789v2/            # Extracted original files
└── arXiv-2307.16789v2_bilingual/  # Translation output
    ├── .translations/             # Translation cache (resume support)
    ├── main.tex                   # LaTeX with translations added
    ├── sections/*.tex             # Translated section files
    └── main.pdf                   # Final bilingual PDF ✓
```

## Command-line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--config_path` | - | Configuration file path (supports YAML/JSON) |
| `--input` | (required) | Input source: arXiv ID, URL, local directory, or archive |
| `--model` | `gpt-5-nano` | Translation model, use `x` for test mode |
| `--target_lang` | `Chinese` | Target language: `Chinese`, `Japanese`, `Korean`, `German`, etc. |
| `--max_workers` | `30` | Maximum concurrent API requests |
| `--resume` | `false` | Resume translation, reuse cached results |
| `--engine` | `auto` | LaTeX engine: `auto`, `xelatex`, `pdflatex` |
| `--toc` | `true` | Add TOC/LOT/LOF at document end |

## FAQ

### Q: What if compilation fails?

Check the terminal error output. Common causes:

- **Missing fonts** (pdfLaTeX): Program automatically adds font fallback
- **Package conflicts**: Program automatically fixes common conflicts (subfigure/natbib/CJK)
- **Missing packages**: Program automatically installs missing LaTeX packages

If XeLaTeX compilation fails, the program will ask if you want to try pdfLaTeX.

### Q: How to switch translation API?

Set the `API_URL` environment variable, API must be OpenAI-compatible:

```bash
export API_URL="https://your-api-endpoint/v1/chat/completions"
```

### Q: Will translation modify original files?

No. Original files are preserved in `tex/arXiv-{id}/` directory, all modifications are made in `tex/arXiv-{id}_bilingual/` directory.

### Q: How does resume translation work?

Translation cache is saved in `.translations/` directory, matched based on paragraph content hash. When using `--resume true`:
- Preserve cache directory
- Re-parse source files
- Skip cached paragraphs
- Only translate new or modified paragraphs

### Q: How to manually compile PDF?

If automatic compilation fails or manual adjustments are needed, use the following commands in the translation output directory (`tex/arXiv-{id}_bilingual/`):

**Method 1: Using XeLaTeX (Recommended, better CJK support)**

```bash
latexmk -xelatex -bibtex -f -interaction=nonstopmode -file-line-error main.tex
```

**Method 2: Using pdfLaTeX (Better compatibility)**

```bash
latexmk -pdf -bibtex -f -interaction=nonstopmode -file-line-error main.tex
```

> **Tips**:
> - `-f`: Continue compilation on errors
> - `-interaction=nonstopmode`: Don't pause for user input
> - `-bibtex`: Automatically process bibliography
> - Compilation will generate `main.pdf`

## License

Apache License 2.0

## Feedback and Contribution

Issues and Pull Requests are welcome!
