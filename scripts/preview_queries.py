import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from france_admission_agent.profile import load_candidate
from france_admission_agent.research.queries import build_discovery_queries

candidate = load_candidate(Path(__file__).resolve().parents[1] / "config" / "candidate_profile.json")
for i, q in enumerate(build_discovery_queries(candidate), 1):
    print(f"{i:02d}. [{q.language}] {q.query}")
