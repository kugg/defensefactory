#!/usr/bin/env python3
"""Run the supported environment-aware installer from the orchestration package."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parents[1] /
                  "skills/defensefactory/scripts/install-defensefactory.py"), run_name="__main__")
