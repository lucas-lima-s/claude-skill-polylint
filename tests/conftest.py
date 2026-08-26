from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
EXAMPLES_DIR = ROOT / "examples" / "sample-project"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
