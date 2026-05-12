"""CLI configuration and entry point."""

import sys
from dataclasses import dataclass, field
from pathlib import Path

import draccus

from translator.arxiv import download_arxiv_source, extract_archive, parse_arxiv_input
from translator.processor import process_paper


@dataclass
class Config:
    """LaTeX paper translator configuration."""

    # Input source: arXiv ID (2307.16789), arXiv URL, local directory, or .tar.gz archive
    input: str = ""
    # Translation model (use "debug" for mock translation without API)
    model: str = "gpt-5-nano"
    # Target language for translation (e.g., Chinese, Japanese, Korean, German)
    target_lang: str = "Chinese"
    # Maximum concurrent API calls
    max_workers: int = 30
    # Continue from previous translation (reuse cached translations)
    resume: bool = False
    # LaTeX engine: xelatex or pdflatex (default: auto-detect from document)
    engine: str = ""
    # Add Table of Contents, List of Tables, List of Figures after \maketitle
    toc: bool = True

    _instance: "Config" = field(default=None, init=False, repr=False)
    debug_mode: bool = field(default=False, init=False, repr=False)
    english_only_mode: bool = field(default=False, init=False, repr=False)

    def __post_init__(self):
        Config._instance = self
        if self.model in ("x", "debug", "none"):
            self.model = "none"
            self.debug_mode = True
        elif self.model == "en":
            self.english_only_mode = True


def print_help_examples():
    """Print common usage examples."""
    examples = """
LaTeX Paper Translator - Common Commands:

  # Download and translate from arXiv (latest version)
  python -m translator --input 2307.16789

  # Download specific version
  python -m translator --input 2307.16789v2

  # From arXiv URL (abs/pdf/src/html all work)
  python -m translator --input https://arxiv.org/abs/2307.16789
  python -m translator --input https://arxiv.org/pdf/2307.16789

  # From local directory
  python -m translator --input tex/arXiv-2511.05271v4

  # From local archive
  python -m translator --input tex/paper.tar.gz

  # Use configuration file (recommended)
  python -m translator --config_path translator/config/default.yaml --input 2307.16789

  # CLI parameters override config file settings
  python -m translator --config_path translator/config/default.yaml --input 2307.16789 --model gpt-4.1-mini --target_lang Japanese

  # Specify target language directly
  python -m translator --input 2307.16789 --target_lang Korean

  # Debug mode (mock translation, no API needed)
  python -m translator --input 2307.16789 --model x

  # Use different model
  python -m translator --input 2307.16789 --model gpt-4.1-mini

  # Resume interrupted translation (reuse cached translations)
  python -m translator --input 2307.16789 --resume true

  # Adjust concurrency (default: 30)
  python -m translator --input 2307.16789 --max_workers 20

  # Force specific LaTeX engine (default: auto-detect from document)
  python -m translator --input 2307.16789 --engine xelatex
  python -m translator --input 2307.16789 --engine pdflatex

  # Add Table of Contents, List of Tables, List of Figures
  python -m translator --input 2307.16789 --toc true

Configuration Files:
  Available config files:
    - translator/config/default.yaml  (default template with detailed comments)

  Create your own config:
    cp translator/config/default.yaml my_config.yaml
    python -m translator --config_path my_config.yaml --input 2307.16789

  Priority: CLI parameters > Config file > Default values

Environment:
  ONE_API    API key for OpenAI-compatible service (required unless --model x/debug/none)
"""
    print(examples)


@draccus.wrap(config_path="translator/config/default.yaml")
def main(cfg: Config):
    """Main entry point."""
    # Show help if no input
    if not cfg.input:
        print_help_examples()
        sys.exit(0)

    input_arg = cfg.input

    if cfg.debug_mode:
        print("Debug mode: using mock translation")
    elif cfg.english_only_mode:
        print("English-only mode: skipping translation, compiling original")
    else:
        print(f"Using model: {cfg.model}")

    if not cfg.english_only_mode:
        print(f"Target language: {cfg.target_lang}")

    # Check if input is an arXiv reference (ID or URL)
    arxiv_id = parse_arxiv_input(input_arg)
    if arxiv_id:
        # Download from arXiv
        tex_dir = Path.cwd() / "tex"
        try:
            archive_path = download_arxiv_source(arxiv_id, tex_dir)
            paper_dir = extract_archive(archive_path)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except RuntimeError as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        # Local file or directory
        input_path = Path(input_arg)

        # Handle relative paths
        if not input_path.is_absolute():
            input_path = Path.cwd() / input_path

        # Check if it's an archive
        if (
            input_path.suffix == ".gz"
            or input_path.name.endswith(".tar.gz")
            or input_path.suffix == ".tgz"
        ):
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
