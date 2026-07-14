#!/usr/bin/env python3
"""Step 2: validate Scenario 1 trajectory files."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.scenario1.validator import main


if __name__ == "__main__":
    main()
