#!/usr/bin/env python3
"""
arXiv paper tools — translation and summarization.

Examples:
    python run.py translate --input 2307.16789
    python run.py translate --input 2307.16789v2
    python run.py translate --input https://arxiv.org/abs/2307.16789
    python run.py translate --input tex/arXiv-2511.05271v4
    python run.py translate --input 2307.16789 --model x           (debug/mock)
    python run.py translate --input 2307.16789 --model gpt-4.1-mini
    python run.py translate --input 2307.16789 --resume true

    python run.py summarize --input 2307.16789
    python run.py summarize --input 2307.16789 --model o3 --reasoning_effort high
"""

import sys

COMMANDS = ("translate", "summarize")


def _usage():
    print(f"Usage: python run.py <{'|'.join(COMMANDS)}> [options]")
    print("       python run.py translate --help")
    print("       python run.py summarize --help")


if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
    _usage()
    sys.exit(0)

cmd = sys.argv[1]
if cmd not in COMMANDS:
    print(f"Unknown command: {cmd!r}")
    _usage()
    sys.exit(1)

# Remove the subcommand so draccus only sees the remaining args.
sys.argv.pop(1)

if cmd == "translate":
    from papercli.translate import main
else:
    from papercli.summarize import main

main()
