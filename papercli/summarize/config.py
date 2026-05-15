"""CLI configuration and entry point for paper summarization."""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import draccus

from papercli.arxiv import download_arxiv_source, extract_archive, parse_arxiv_input
from papercli.summarize.runner import PROJECT_ROOT, run_summary


@dataclass
class SummarizeConfig:
    # Input: arXiv ID (2307.16789), arXiv URL, or local directory
    input: str = ""
    # Prompt file: bare name (looked up in papercli/summarize/prompts/), or absolute path.
    # .md suffix is auto-completed if omitted.
    prompt_file: str = "general"
    # Codex model to use
    model: str = "gpt-5.5"
    # Reasoning effort: low, medium, high, xhigh
    reasoning_effort: str = "xhigh"

    def __post_init__(self):
        # draccus uses YAML to parse CLI values, which converts e.g. "2511.14460"
        # to float 2511.1446, dropping the trailing zero. Re-read from sys.argv directly.
        for i, arg in enumerate(sys.argv[:-1]):
            if arg == "--input":
                raw = sys.argv[i + 1]
                if re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", raw):
                    self.input = raw
                break


def _print_help():
    print("""
Paper Summarizer - Common Commands:

  python run.py summarize --input 2307.16789
  python run.py summarize --input 2307.16789 --model o3 --reasoning_effort high
  python run.py summarize --input tex/my-paper/ --prompt_file my_prompt
  python run.py summarize --input tex/my-paper/ --prompt_file /abs/path/to/my_prompt.md
  python run.py summarize --input https://arxiv.org/abs/2307.16789
""")


@draccus.wrap()
def main(cfg: SummarizeConfig):
    """Main entry point for paper summarization."""
    if not cfg.input:
        _print_help()
        sys.exit(0)

    arxiv_id = parse_arxiv_input(cfg.input)
    if arxiv_id:
        tex_dir = PROJECT_ROOT / "tex"
        archive_path = download_arxiv_source(arxiv_id, tex_dir)
        paper_dir = extract_archive(archive_path)
        label = arxiv_id
    else:
        paper_dir = Path(cfg.input)
        if not paper_dir.is_absolute():
            paper_dir = PROJECT_ROOT / paper_dir
        if not paper_dir.exists():
            print(f"Error: not found: {paper_dir}")
            sys.exit(1)
        label = paper_dir.name

    run_summary(paper_dir, cfg, label)
