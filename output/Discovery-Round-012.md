# France Master's Research — Discovery Round 12 Report

> **Mode**: Single Bounded Iterative Discovery Round
> **Strategy**: Expansion into under-explored regional public universities with lower competition pressure.

## 1. Round Execution & Stop Reason
- **Round Stop Reason:** `BOUNDED_LOW_YIELD`
- **Stop Preconditions Satisfied:** YES
  - **Actual searches used:** 4
  - **Actual low-value searches:** 3
  - **Distinct frontiers attempted:** 4
- **Selected Regions:** Occitanie, Auvergne-Rhône-Alpes, Centre-Val de Loire
- **Distinct Regions Actually Searched:** 1
- **Distinct Cities Actually Searched:** 4
- **New Search Frontiers Generated:** 4
- **Universities Attempted:** 4 (Université de Montpellier, Université Toulouse III - Paul Sabatier, Université de Nîmes, Université de Perpignan Via Domitia)
- **New Universities:** 0
- **Known Universities With New Tracks:** 1
- **New Programmes:** 1
- **Deeply Verified Programmes:** 0
- **Remaining Search Budget:** 8
- **Regions Recommended for Next Bounded Round:** Corse, Centre-Val de Loire, Bourgogne-Franche-Comté

## 2. Search & Token Efficiency Metrics
- **External Search Calls Actually Executed:** 4
- **Provider Calls Attempted:** 4
- **Provider Calls Successful:** 4
- **Provider Failures:** 0
- **Queries Blocked as Exact Duplicates:** 0
- **Queries Rewritten After Duplication:** 0
- **Searches Saved by Verified Memory:** 0
- **Cache Hits:** 0
- **Fields Resolved:** 0
- **Evidence Gain per Search:** 0.0
- **Tokens Used:** 0 (Local deterministic parsing)

## 3. Discovered Programmes in This Round

| University | Programme / Track | Region | Degree Fit | Instruction Language | Profile Fit | Opportunity Quality |
|---|---|---|---|---|---:|---|
| Université de Montpellier | Master Informatique (Unspecified track) | Occitanie | UNVERIFIED | LANGUAGE_UNVERIFIED | UNASSESSED | PENDING_PIPELINE |

## Incremental pipeline

| Metric | Value |
|---|---:|
| migrated_records | 0 |
| repaired_cycle1_records | 0 |
| cycle1_processed | 1 |
| cycle1_passed | 0 |
| cycle1_rejected | 0 |
| cycle1_review_required | 1 |
| cycle1_deferred | 0 |
| promoted_to_cycle2 | 0 |
| cycle2_processed | 0 |
| cycle2_verified | 0 |
| cycle2_rejected | 0 |
| fields_refreshed | 0 |
| pool_additions | 0 |
| pool_replacements | 0 |
| pool_unchanged_candidates | 0 |
| errors | 0 |
| external_searches | 4 |
| cache_hits | 3 |
| searches_saved_by_memory | 1 |
| llm_calls | 0 |
| input_tokens | 0 |
| output_tokens | 0 |
| provider_failures | 0 |
| page_fetches | 6 |
| cycle1_searches | 4 |
| cycle2_searches | 0 |
| current_pool_size | 0 |
| new_programmes_per_round | 1 |
| promoted_programmes_per_round | 0 |
| pool_replacements_per_round | 0 |
| legacy_records_reviewed_without_cycle1_rerun | 0 |
| legacy_first_cycle2_processed | 0 |
| new_delta_promoted_to_cycle2 | 0 |
| consecutive_rounds_without_pool_improvement | 3 |
| regions_explored | 11 |
| final_selection_ready | False |

Pipeline stop reason: `BOUNDED_LOW_YIELD`. No next discovery round was started.

### Exact stage transitions

| Programme ID | From | To | Reason |
|---|---|---|---|
| a1a15131766cf69a | CYCLE1_PENDING | CYCLE1_PROCESSING | Incremental Cycle 1 |
| a1a15131766cf69a | CYCLE1_PROCESSING | CYCLE1_REVIEW_REQUIRED | Evidence-backed eligibility screening |
