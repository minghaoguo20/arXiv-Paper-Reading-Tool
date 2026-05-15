"""CLI configuration and entry point for translation."""

import sys
from dataclasses import dataclass, field
import re
from pathlib import Path

import draccus

from papercli.arxiv import download_arxiv_source, extract_archive, parse_arxiv_input
from papercli.translate.processor import process_paper


@dataclass
class TranslateConfig:
    """LaTeX paper translator configuration."""

    # Input source: arXiv ID (2307.16789), arXiv URL, local directory, or .tar.gz archive
    input: str = ""
    # Translation model (use "debug" for mock translation without API)
    model: str = "gpt-4.1-nano"
    # API provider: blt, rightcode, auto (detect from env)
    provider: str = "blt"
    # Target language for translation (e.g., Chinese, Japanese, Korean, German)
    target_lang: str = "Chinese"
    # Maximum concurrent API calls
    max_workers: int = 30
    # Continue from previous translation (reuse cached translations)
    resume: bool = False
    # LaTeX engine: xelatex or pdflatex (default: auto-detect from document)
    engine: str = ""
    # Add Table of Contents, List of Tables, List of Figures after \maketitle
    toc: bool = False

    _instance: "TranslateConfig" = field(default=None, init=False, repr=False)
    debug_mode: bool = field(default=False, init=False, repr=False)
    english_only_mode: bool = field(default=False, init=False, repr=False)

    def __post_init__(self):
        TranslateConfig._instance = self
        # draccus uses YAML to parse CLI values, which converts e.g. "2511.14460"
        # to float 2511.1446, dropping the trailing zero. Re-read from sys.argv directly.
        for i, arg in enumerate(sys.argv[:-1]):
            if arg == "--input":
                raw = sys.argv[i + 1]
                if re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", raw):
                    self.input = raw
                break
        if self.model in ("x", "debug", "none"):
            self.model = "none"
            self.debug_mode = True
        elif self.model == "en":
            self.english_only_mode = True
        import os as _os
        if self.model == "gpt-4.1-nano" and (
            self.provider == "rightcode"
            or (self.provider == "auto" and _os.environ.get("RIGHTCODE_API"))
        ):
            self.model = "gpt-5.4-mini"


def _print_help():
    print("""
LaTeX Paper Translator - Common Commands:

  python run.py translate --input 2307.16789
  python run.py translate --input 2307.16789v2
  python run.py translate --input https://arxiv.org/abs/2307.16789
  python run.py translate --input tex/arXiv-2511.05271v4
  python run.py translate --input tex/paper.tar.gz
  python run.py translate --input 2307.16789 --model x          (debug/mock)
  python run.py translate --input 2307.16789 --model gpt-4.1-mini
  python run.py translate --input 2307.16789 --target_lang Japanese
  python run.py translate --input 2307.16789 --resume true
  python run.py translate --input 2307.16789 --max_workers 20
  python run.py translate --input 2307.16789 --engine xelatex
  python run.py translate --input 2307.16789 --toc true

Config file:
  python run.py translate --config_path papercli/translate/config/default.yaml --input 2307.16789

Environment:
  ONE_API         API key for blt/OpenAI-compatible service
  API_URL         Base URL for blt/OpenAI-compatible service
  RIGHTCODE_API   API key for right.codes (auto-detected when set)
  RIGHTCODE_URL   Base URL for right.codes
""")


@draccus.wrap(config_path="papercli/translate/config/default.yaml")
def main(cfg: TranslateConfig):
    """Main entry point for translation."""
    if not cfg.input:
        _print_help()
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

    arxiv_id = parse_arxiv_input(input_arg)
    if arxiv_id:
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
        input_path = Path(input_arg)

        if not input_path.is_absolute():
            input_path = Path.cwd() / input_path

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
