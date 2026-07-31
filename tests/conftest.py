"""Test configuration."""

import sys
from pathlib import Path

# Add backend to path for imports
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
