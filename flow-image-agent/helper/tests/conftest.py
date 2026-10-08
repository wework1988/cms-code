from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIBS = ROOT / ".python-libs"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if LIBS.is_dir() and str(LIBS) not in sys.path:
    sys.path.insert(0, str(LIBS))
