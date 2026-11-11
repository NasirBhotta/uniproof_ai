from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from france_admission_agent.pipeline.cli import main
if __name__ == '__main__':
    main('pool')
