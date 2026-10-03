import sys
from pathlib import Path

# Add project root and src to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from examples.run_with_antigravity import main as run_agent


def main():
    run_agent()


if __name__ == "__main__":
    main()

