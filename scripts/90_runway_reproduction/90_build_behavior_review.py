#!/usr/bin/env python3
"""Historical Step 90: build the runway behavior-review packet."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.behavior_review import main


if __name__ == "__main__":
    main()
