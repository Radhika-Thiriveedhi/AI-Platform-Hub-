"""AI Platform Hub - Root Application Entry Point."""
import os
import sys
from pathlib import Path

# Configure paths
ROOT_DIR = Path(__file__).resolve().parent
INNER_DIR = ROOT_DIR / "ai_platform_hub_50k_loc_fixed"

if str(INNER_DIR) not in sys.path:
    sys.path.insert(0, str(INNER_DIR))

os.chdir(str(INNER_DIR))

from run import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
