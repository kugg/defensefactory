#!/usr/bin/env python3
"""Stable public entrypoint for the versioned RULES.md compiler."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name("claim-rules-v1.py")), run_name="__main__")
