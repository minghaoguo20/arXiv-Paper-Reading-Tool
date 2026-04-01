#!/usr/bin/env python3
"""
LaTeX Paper Translator - Translates LaTeX papers to bilingual PDF via tectonic.

Examples:
    # arXiv ID (auto-download latest version)
    python translate.py --input 2307.16789

    # arXiv ID with specific version
    python translate.py --input 2307.16789v2

    # arXiv URL (abs/pdf/src/html)
    python translate.py --input https://arxiv.org/abs/2307.16789

    # Local directory
    python translate.py --input tex/arXiv-2511.05271v4

    # Local archive
    python translate.py --input tex/arXiv-2402.01030v4.tar.gz

    # Debug mode (mock translation, no API call)
    python translate.py --input 2307.16789 --model x

    # Custom model
    python translate.py --input 2307.16789 --model gpt-4.1-mini

    # Resume interrupted translation
    python translate.py --input 2307.16789 --resume true

Environment:
    ONE_API - API key for OpenAI-compatible service (required unless --model x/debug/none)
"""

from translator import main

if __name__ == "__main__":
    main()
