# Cycle 1 pipeline verification

Every incremental round follows discovery -> saved Cycle 1 research and scores -> comparison with eligible saved Cycle 1 candidates -> ranked promotion -> Cycle 2 -> verified working pool.

1. Discovery: bind institution to official source domain, discard aggregator identity guesses, and retain explicit track names. An unspecified track is a lead, not a verified programme. No synthetic admission scores or capacity are populated.
2. Cycle 1: use the existing LangGraph validators and score calculation. Official scoped degree and M1 evidence are required for PASSED. Missing evidence is REVIEW_REQUIRED; unavailable provider or exhausted budget leaves work PENDING. Research snapshots and evidence survive retry.
3. Scoring: retain fit and evidence-confidence scores separately. Unknown dimensions are visible and never count as an advantage.
4. Comparison: compare against saved eligible Cycle 1 snapshots, including earlier rounds, independently of the deep pool. Preserve the original Cycle 1 vector when Cycle 2 updates its own research. Record compared IDs, decision, reason and rank in SQLite.
5. Ranking: evidence gates first, Pareto tiers next, evidence-confidence and fit scores as tie breakers. A deterministic top representative can advance when new candidates tie. This is an opportunity ranking, not an admission probability.
6. Cycle 2: only promoted candidates enter; process their saved ranks first. Keep the existing stricter verified-pool evidence requirements.
7. Reporting: Cycle1-Detailed-Latest.md reuses the original detailed report renderer. Cycle1-Ranking.md / .json include saved analyses and unresolved dimensions. These are snapshots of existing evidence, not claims of a new live verification.

## Existing database audit

Backup: see Cycle1-Repair-Audit.json. All 116 programme IDs preserved. Repaired 25 premature incremental-1 passes: 10 official-source records pending research and 15 needing source/evidence review. There are 44 saved Cycle 1 analyses; 3 currently meet comparison gates. 72 legacy rows have no completed imported analysis and remain LEGACY_REVIEW.

No live discovery or provider searches were run during this repair. Automated regression tests exercise mocked providers and database transitions; they do not prove admissions facts or complete live research. Extraction remains conservative and may miss official wording, PDF-only evidence, redirected sources or alternate institution domains. Review unresolved evidence rather than increasing scores to fill the shortlist.

## Run the repaired queue

From the activated project environment:

```powershell
python run_cycle1.py --pending-only --search-budget 12
```

Inspect Cycle1-Detailed-Latest.md, Cycle1-Ranking.md and Pipeline-Latest.json. Repeat pending-only runs while work remains pending. Budget is per invocation, not per programme. REVIEW_REQUIRED does not retry automatically; use `python run_cycle1.py --retry-review PROGRAMME_ID --search-budget 12` for a selected record after checking its source identity. Source identity corrections must preserve provenance; retry alone cannot fix a wrong programme URL.

Then run `python run_cycle2.py --pending-only --search-budget 12`. Future normal discovery rounds use this same incremental pipeline automatically. Manual Cycle 1 promotes eligible ranked candidates but does not execute Cycle 2 research.
