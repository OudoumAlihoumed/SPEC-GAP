#!/usr/bin/env python3
"""Step 3: validate, cache, or run one Qwen3-32B model turn on Modal."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.infrastructure.modal_qwen_runner import app, main


__all__ = ["app", "main"]
