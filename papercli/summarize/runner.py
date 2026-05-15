"""Paper summarization logic."""

from __future__ import annotations

import os
import platform
import signal
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from papercli.summarize.config import SummarizeConfig

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def resolve_prompt_path(prompt_file: str) -> Path:
    """Resolve prompt file path.

    Resolution order:
    1. Absolute path (with optional .md auto-complete)
    2. Bare name / relative path under PROMPTS_DIR (with optional .md auto-complete)
    3. Relative path under PROJECT_ROOT (with optional .md auto-complete)
    """
    p = Path(prompt_file)

    def _try_with_md(candidate: Path) -> Path | None:
        if candidate.exists():
            return candidate
        if candidate.suffix != ".md":
            with_md = candidate.parent / (candidate.name + ".md")
            if with_md.exists():
                return with_md
        return None

    if p.is_absolute():
        resolved = _try_with_md(p)
        return resolved if resolved is not None else p

    # Try under PROMPTS_DIR first
    resolved = _try_with_md(PROMPTS_DIR / p)
    if resolved is not None:
        return resolved

    # Fallback: relative to PROJECT_ROOT
    resolved = _try_with_md(PROJECT_ROOT / p)
    return resolved if resolved is not None else PROMPTS_DIR / p


def _slug(label: str) -> str:
    return label.replace("/", "_").replace(".", "_")


def run_summary(paper_dir: Path, cfg: "SummarizeConfig", label: str = "") -> None:
    prompt_path = resolve_prompt_path(cfg.prompt_file)
    if not prompt_path.exists():
        print(f"Error: prompt file not found: {prompt_path}")
        sys.exit(1)
    prompt = prompt_path.read_text(encoding="utf-8")

    display_label = label or paper_dir.name
    full_input = (
        f"{prompt}\n\n"
        f"---\n\n"
        f"# {display_label}\n\n"
        f"Read the LaTeX source files in the current directory, then write the summary report."
    )

    output_dir = paper_dir.parent / f"{paper_dir.name}_summary"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{_slug(display_label)}.md"

    if output_file.exists():
        answer = input(f"Summary already exists: {output_file}\nRe-summarize? [y/N] ").strip().lower()
        if answer != "y":
            print(f"Opening existing summary: {output_file}")
            if platform.system() == "Darwin":
                subprocess.run(["open", str(output_file)])
            return

    print(f"Running codex (model={cfg.model}, reasoning={cfg.reasoning_effort}) ...")
    proc = subprocess.Popen(
        [
            "codex", "exec",
            "-m", cfg.model,
            "-c", f"model_reasoning_effort={cfg.reasoning_effort}",
            "--ephemeral",
            "-s", "read-only",
            "--skip-git-repo-check",
            "-o", str(output_file),
        ],
        stdin=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        cwd=paper_dir,
        preexec_fn=os.setsid,
    )
    try:
        proc.communicate(input=full_input, timeout=1800)  # 30 min ceiling
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.communicate()
        print("codex timed out after 30 minutes")
        return
    result = proc

    if result.returncode != 0:
        print(f"codex exited with code {result.returncode}")
    else:
        print(f"Saved -> {output_file}")
        if platform.system() == "Darwin":
            subprocess.run(["open", str(output_file)])
