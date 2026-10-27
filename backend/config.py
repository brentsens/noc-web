from pathlib import Path


HOME = Path.home()

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FRONTEND_ROOT = PROJECT_ROOT / "frontend"

NOC_ROOT = HOME / "noc"

NOC_BIN = HOME / ".local" / "bin"