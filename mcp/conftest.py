"""Test bootstrap: expose api/app on sys.path for cross-process roundtrip tests."""

import sys
from pathlib import Path

_API_SRC = Path(__file__).resolve().parent.parent / "api"
if _API_SRC.is_dir():
    sys.path.insert(0, str(_API_SRC))
