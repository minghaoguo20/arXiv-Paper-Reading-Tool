"""LaTeX Paper Translator - Translates LaTeX papers to bilingual PDF."""

from dotenv import load_dotenv

# Load .env file if it exists (does not override existing environment variables)
load_dotenv()

from translator.cli import Config, main

__all__ = ["Config", "main"]
