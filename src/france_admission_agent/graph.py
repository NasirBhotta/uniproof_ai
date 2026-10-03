from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .scoring import assign_evaluation_group, calculate_score, classification
from .schemas import CheckStatus, CycleStatus, ProgrammeEvaluation
from .state import ResearchState
from .validators import (
    determine_cycle_readiness,
    is_final_ready,
    run_full_validation_layer,
    validate_hard_eligibility,
)


def build_graph(backend):
    def discover(state):
        seen = {p.programme_id for p in state.get("programmes", [])}
        batch = backend.discover_programmes(
            state["candidate"],
            state.get("discovery_batch_size", 25),
            seen,
        )
        return {
            "programmes": state.get("programmes", []) + [
                p for p in batch if p.programme_id not in seen
            ],
            "discovery_round": state.get("discovery_round", 0) + 1,
        }

    def evaluate(state):
        done = {
            e.programme.programme_id
            for e in state.get("evaluations", []) + state.get("rejected", [])
        }
        survivors = list(state.get("evaluations", []))
        rejected = list(state.get("rejected", []))

        for raw in state.get("programmes", []):
            if raw.programme_id in done:
                continue

            # 1. Retrieve official evidence, extract all fields, targeted resolution
            p = backend.enrich_and_verify(state["candidate"], raw)

            # 2. Hard eligibility check (UNKNOWN != FAIL)
            elig = validate_hard_eligibility(state["candidate"], p)
            cycle_status, _ = determine_cycle_readiness(state["candidate"], p)

            e = ProgrammeEvaluation(
                programme=p,
                eligibility=elig,
                cycle_readiness=cycle_status,
            )

            if elig.hard_fail:
                e.rejected = True
                e.group = "E_REJECTED"
                e.classification = "Rejected"
                e.rejection_reasons.extend(elig.reasons)
                rejected.append(e)
                continue

            # 3. Transcript matching
            e.curriculum_coverage = backend.transcript_coverage(state["candidate"], p)

            # 4. Adversarial skeptic review
            e.skeptic = backend.skeptic_review(state["candidate"], e)
            if e.skeptic.fatal_issue:
                e.rejected = True
                e.group = "E_REJECTED"
                e.classification = "Rejected"
                e.rejection_reasons.extend(e.skeptic.serious_risks)
                rejected.append(e)
                continue

            # 5. Validation layer before scoring (Section 21)
            val_status, val_notes = run_full_validation_layer(state["candidate"], p)
            e.validation_status = val_status
            e.validation_notes = val_notes

            # 6. Split scoring: Profile Fit vs Evidence Confidence
            e.final_ready = is_final_ready(e.eligibility, e.skeptic.unresolved_questions) and val_status == CheckStatus.PASS
            e.score = calculate_score(e)
            e.group = assign_evaluation_group(e)
            e.classification = classification(e.score.profile_fit_score, e.final_ready, e.group)

            survivors.append(e)

        return {"evaluations": survivors, "rejected": rejected}

    def route(state):
        # Viable programmes are Group A, Group B, and Group C (Section 4 & 18)
        viable = [
            e for e in state.get("evaluations", [])
            if e.group in ("A_FULLY_VERIFIED", "B_CALENDAR_PENDING", "C_LANGUAGE_VERIFICATION_REQUIRED") and not e.rejected
        ]
        target = state.get("target_count", 7)

        if len(viable) >= target:
            return "finalize"
        if state.get("discovery_round", 0) >= state.get("max_discovery_rounds", 3):
            return "finalize"
        return "discover"

    def finalize(state):
        evals = state.get("evaluations", [])

        # Priority for final shortlist: Group A first, then Group B, then Group C
        group_a = sorted(
            [e for e in evals if e.group == "A_FULLY_VERIFIED" and not e.rejected],
            key=lambda e: e.score.profile_fit_score,
            reverse=True,
        )
        group_b = sorted(
            [e for e in evals if e.group == "B_CALENDAR_PENDING" and not e.rejected],
            key=lambda e: e.score.profile_fit_score,
            reverse=True,
        )
        group_c = sorted(
            [e for e in evals if e.group == "C_LANGUAGE_VERIFICATION_REQUIRED" and not e.rejected],
            key=lambda e: e.score.profile_fit_score,
            reverse=True,
        )

        target = state.get("target_count", 7)
        shortlist = (group_a + group_b + group_c)[:target]

        reason = (
            f"Successfully identified {len(shortlist)} strong-fit regional programmes "
            f"({len(group_a)} fully verified, {len(group_b)} calendar pending, {len(group_c)} language verification required)."
            if shortlist
            else f"Identified 0 viable survivors after {state.get('discovery_round', 0)} discovery rounds."
        )

        # Attach backend efficiency metrics to state
        metrics = backend.get_metrics(len(evals) + len(state.get("rejected", []))) if hasattr(backend, "get_metrics") else {}

        return {
            "final_shortlist": shortlist,
            "stop_reason": reason,
            "metrics": metrics,
        }


    b = StateGraph(ResearchState)
    b.add_node("discover", discover)
    b.add_node("evaluate", evaluate)
    b.add_node("finalize", finalize)
    b.add_edge(START, "discover")
    b.add_edge("discover", "evaluate")
    b.add_conditional_edges(
        "evaluate",
        route,
        {"discover": "discover", "finalize": "finalize"},
    )
    b.add_edge("finalize", END)
    return b.compile()
