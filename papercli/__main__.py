"""Entry point for python -m papercli."""

print("""
papercli - arXiv paper tools

Subcommands:
  python run.py translate   Translate a LaTeX paper to bilingual PDF
  python run.py summarize   Summarize a LaTeX paper

Examples:
  python run.py translate --input 2307.16789
  python run.py summarize --input 2307.16789
""")
