# arXiv Paper Toolkit

[English](README.md) | [中文](README-zh.md)

Download arXiv papers and translate them into bilingual PDFs or generate structured summaries.

![example](example/example.png)

## Sub-commands

| Command | Description | Docs |
|---------|-------------|------|
| `translate` | Translate to bilingual PDF, preserving math and LaTeX formatting | [Details](papercli/translate/README-zh.md) |
| `summarize` | Generate a structured summary using a Codex model | [Details](papercli/summarize/README-zh.md) |

## Installation

**Python dependencies**

```bash
pip install -r requirements.txt
```

**LaTeX compiler** (required for `translate`)

We recommend TinyTeX:

```bash
curl -sL "https://yihui.org/tinytex/install-bin-unix.sh" | sh
tlmgr install cjk ctex xecjk fontspec
```

**Environment variables**

```bash
cp .env.example .env
# Edit .env and fill in your API Key
```

## Quick Start

```bash
# Translate a paper
python run.py translate --input 2307.16789

# Summarize a paper
python run.py summarize --input 2307.16789
```

## Compatibility

Tested on macOS; Linux should work. Windows users may need to adjust installation steps. Translation success is not guaranteed for all arXiv papers due to diverse LaTeX formats.

## License

Apache License 2.0
