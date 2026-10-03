from __future__ import annotations

from pathlib import Path

from .graph import build_graph
from .profile import load_candidate
from .reporting import save_run_outputs


def run_research(
    backend,
    *,
    candidate_path: str | Path = "config/candidate_profile.json",
    output_dir: str | Path = "output",
    target_count: int = 7,
    discovery_batch_size: int = 20,
    max_discovery_rounds: int = 4,
):
    candidate = load_candidate(candidate_path)
    graph = build_graph(backend)
    result = graph.invoke({
        "candidate": candidate,
        "target_count": target_count,
        "discovery_batch_size": discovery_batch_size,
        "max_discovery_rounds": max_discovery_rounds,
        "discovery_round": 0,
        "programmes": [],
        "evaluations": [],
        "rejected": [],
    })
    paths = save_run_outputs(result, output_dir, target_intake=candidate.target.intake)
    return result, paths
