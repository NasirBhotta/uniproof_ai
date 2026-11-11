# France Master's Research — Discovery Round 8 Report

> **Mode**: Single Bounded Iterative Discovery Round
> **Strategy**: Expansion into under-explored regional public universities with lower competition pressure.

## 1. Round Execution & Stop Reason
- **Round Stop Reason:** `FRONTIERS_DEFERRED`
- **Stop Preconditions Satisfied:** YES
- **Selected Regions:** Centre-Val de Loire, Bourgogne-Franche-Comté, Normandie
- **Distinct Regions Actually Searched:** 3
- **Distinct Cities Actually Searched:** 7
- **New Search Frontiers Generated:** 7
- **Universities Attempted:** 7 (Université d'Orléans, Université de Rouen Normandie, Université de Franche-Comté, Université de Caen Normandie, Université Le Havre Normandie, Université de Bourgogne, Université de Tours)
- **New Universities:** 0
- **Known Universities With New Tracks:** 4
- **New Programmes:** 6
- **Deeply Verified Programmes:** 0
- **Remaining Search Budget:** 5
- **Regions Recommended for Next Bounded Round:** Corse, Centre-Val de Loire, Bourgogne-Franche-Comté

## 2. Search & Token Efficiency Metrics
- **External Search Calls Actually Executed:** 7
- **Provider Calls Attempted:** 7
- **Provider Calls Successful:** 7
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
| Université d'Orléans | Master Informatique (Science des Données et IA) | Centre-Val de Loire | UNVERIFIED | LANGUAGE_UNVERIFIED | UNASSESSED | PENDING_PIPELINE |
| Université de Rouen Normandie | Master Informatique (Science des Données et IA) | Normandie | UNVERIFIED | LANGUAGE_UNVERIFIED | UNASSESSED | PENDING_PIPELINE |
| Université de Caen Normandie | Master Informatique (Science des Données et IA) | Normandie | UNVERIFIED | LANGUAGE_UNVERIFIED | UNASSESSED | PENDING_PIPELINE |
| Université de Caen Normandie | Master Informatique (Tronc Commun / Parcours Informatique Générale) | Normandie | UNVERIFIED | LANGUAGE_UNVERIFIED | UNASSESSED | PENDING_PIPELINE |
| Université Le Havre Normandie | Master Informatique (Systèmes Distribués et Réseaux) | Normandie | UNVERIFIED | LANGUAGE_UNVERIFIED | UNASSESSED | PENDING_PIPELINE |
| Université Le Havre Normandie | Master Informatique (Science des Données et IA) | Normandie | UNVERIFIED | LANGUAGE_UNVERIFIED | UNASSESSED | PENDING_PIPELINE |

## Incremental pipeline

| Metric | Value |
|---|---:|
| migrated_records | 0 |
| cycle1_processed | 6 |
| cycle1_passed | 6 |
| cycle1_rejected | 0 |
| promoted_to_cycle2 | 1 |
| cycle2_processed | 1 |
| cycle2_verified | 0 |
| cycle2_rejected | 0 |
| fields_refreshed | 0 |
| pool_additions | 0 |
| pool_replacements | 0 |
| pool_unchanged_candidates | 20 |
| errors | 0 |
| external_searches | 10 |
| cache_hits | 4 |
| searches_saved_by_memory | 1 |
| llm_calls | 0 |
| input_tokens | 0 |
| output_tokens | 0 |
| provider_failures | 0 |
| page_fetches | 6 |
| cycle1_searches | 6 |
| cycle2_searches | 4 |
| current_pool_size | 0 |
| new_programmes_per_round | 6 |
| promoted_programmes_per_round | 1 |
| pool_replacements_per_round | 0 |
| legacy_records_reviewed_without_cycle1_rerun | 14 |
| legacy_first_cycle2_processed | 1 |
| new_delta_promoted_to_cycle2 | 0 |
| consecutive_rounds_without_pool_improvement | 1 |
| regions_explored | 3 |
| final_selection_ready | False |

Pipeline stop reason: `FRONTIERS_DEFERRED`. No next discovery round was started.

### Exact stage transitions

| Programme ID | From | To | Reason |
|---|---|---|---|
| 349990842acda180 | CYCLE1_PENDING | CYCLE1_PROCESSING | Incremental Cycle 1 |
| 349990842acda180 | CYCLE1_PROCESSING | CYCLE1_PASSED | Evidence-backed eligibility screening |
| 40a29659ad41f697 | CYCLE1_PENDING | CYCLE1_PROCESSING | Incremental Cycle 1 |
| 40a29659ad41f697 | CYCLE1_PROCESSING | CYCLE1_PASSED | Evidence-backed eligibility screening |
| 979dc10f9d2258da | CYCLE1_PENDING | CYCLE1_PROCESSING | Incremental Cycle 1 |
| 979dc10f9d2258da | CYCLE1_PROCESSING | CYCLE1_PASSED | Evidence-backed eligibility screening |
| b77bbe2ae231b9c5 | CYCLE1_PENDING | CYCLE1_PROCESSING | Incremental Cycle 1 |
| b77bbe2ae231b9c5 | CYCLE1_PROCESSING | CYCLE1_PASSED | Evidence-backed eligibility screening |
| c77b4272d79a465e | CYCLE1_PENDING | CYCLE1_PROCESSING | Incremental Cycle 1 |
| c77b4272d79a465e | CYCLE1_PROCESSING | CYCLE1_PASSED | Evidence-backed eligibility screening |
| faf1ec48a8b1515b | CYCLE1_PENDING | CYCLE1_PROCESSING | Incremental Cycle 1 |
| faf1ec48a8b1515b | CYCLE1_PROCESSING | CYCLE1_PASSED | Evidence-backed eligibility screening |
| 1dd0d15beb2379a6 | CYCLE1_PASSED | PROMOTION_REVIEW | Compare saved dimensions |
| 1dd0d15beb2379a6 | PROMOTION_REVIEW | POOL_DROPPED | INSUFFICIENT_EVIDENCE: No evidence of academic or degree compatibility yet |
| 241542b76c0fe682 | CYCLE1_PASSED | PROMOTION_REVIEW | Compare saved dimensions |
| 241542b76c0fe682 | PROMOTION_REVIEW | POOL_DROPPED | INSUFFICIENT_EVIDENCE: No evidence of academic or degree compatibility yet |
| 6cdf0e7da2bd2357 | CYCLE1_PASSED | PROMOTION_REVIEW | Compare saved dimensions |
| 6cdf0e7da2bd2357 | PROMOTION_REVIEW | CYCLE2_PENDING | COMPLEMENT_EXISTING: Build a credible working pool |
| d1172ed14d796c1a | CYCLE1_PASSED | PROMOTION_REVIEW | Compare saved dimensions |
| d1172ed14d796c1a | PROMOTION_REVIEW | POOL_DROPPED | INSUFFICIENT_EVIDENCE: No evidence of academic or degree compatibility yet |
| dd14b0cc5ef4d577 | CYCLE1_PASSED | PROMOTION_REVIEW | Compare saved dimensions |
| dd14b0cc5ef4d577 | PROMOTION_REVIEW | POOL_DROPPED | INSUFFICIENT_EVIDENCE: No evidence of academic or degree compatibility yet |
| e88178bda5ea2cc3 | CYCLE1_PASSED | PROMOTION_REVIEW | Compare saved dimensions |
| e88178bda5ea2cc3 | PROMOTION_REVIEW | POOL_DROPPED | INSUFFICIENT_EVIDENCE: No evidence of academic or degree compatibility yet |
| 349990842acda180 | CYCLE1_PASSED | PROMOTION_REVIEW | Compare saved dimensions |
| 349990842acda180 | PROMOTION_REVIEW | POOL_DROPPED | INSUFFICIENT_EVIDENCE: No evidence of academic or degree compatibility yet |
| 40a29659ad41f697 | CYCLE1_PASSED | PROMOTION_REVIEW | Compare saved dimensions |
| 40a29659ad41f697 | PROMOTION_REVIEW | POOL_DROPPED | INSUFFICIENT_EVIDENCE: No evidence of academic or degree compatibility yet |
| 979dc10f9d2258da | CYCLE1_PASSED | PROMOTION_REVIEW | Compare saved dimensions |
| 979dc10f9d2258da | PROMOTION_REVIEW | POOL_DROPPED | INSUFFICIENT_EVIDENCE: No evidence of academic or degree compatibility yet |
| b77bbe2ae231b9c5 | CYCLE1_PASSED | PROMOTION_REVIEW | Compare saved dimensions |
| b77bbe2ae231b9c5 | PROMOTION_REVIEW | POOL_DROPPED | INSUFFICIENT_EVIDENCE: No evidence of academic or degree compatibility yet |
| c77b4272d79a465e | CYCLE1_PASSED | PROMOTION_REVIEW | Compare saved dimensions |
| c77b4272d79a465e | PROMOTION_REVIEW | POOL_DROPPED | INSUFFICIENT_EVIDENCE: No evidence of academic or degree compatibility yet |
| faf1ec48a8b1515b | CYCLE1_PASSED | PROMOTION_REVIEW | Compare saved dimensions |
| faf1ec48a8b1515b | PROMOTION_REVIEW | POOL_DROPPED | INSUFFICIENT_EVIDENCE: No evidence of academic or degree compatibility yet |
| 6cdf0e7da2bd2357 | CYCLE2_PENDING | CYCLE2_PROCESSING | Promoted challenger only |
| 6cdf0e7da2bd2357 | CYCLE2_PROCESSING | CYCLE2_REVIEW_REQUIRED | Deep targeted checks completed |
| f5dc94180ae92f56 | CYCLE2_REVIEW_REQUIRED | POOL_DROPPED | INSUFFICIENT_EVIDENCE: Critical evidence remains unresolved or stale |
| 4cb77900ea4201bd | CYCLE2_REVIEW_REQUIRED | POOL_DROPPED | INSUFFICIENT_EVIDENCE: Critical evidence remains unresolved or stale |
| ca9adec2279cd309 | CYCLE2_REVIEW_REQUIRED | POOL_DROPPED | INSUFFICIENT_EVIDENCE: Critical evidence remains unresolved or stale |
| c6e84287c4366383 | CYCLE2_REVIEW_REQUIRED | POOL_DROPPED | INSUFFICIENT_EVIDENCE: Critical evidence remains unresolved or stale |
| da5e59fd2e1c82a7 | CYCLE2_REVIEW_REQUIRED | POOL_DROPPED | INSUFFICIENT_EVIDENCE: Critical evidence remains unresolved or stale |
| 1398c04d118bab69 | CYCLE2_REVIEW_REQUIRED | POOL_DROPPED | INSUFFICIENT_EVIDENCE: Critical evidence remains unresolved or stale |
| 6cdf0e7da2bd2357 | CYCLE2_REVIEW_REQUIRED | POOL_DROPPED | INSUFFICIENT_EVIDENCE: Critical evidence remains unresolved or stale |
| 085e2e20b37f2190 | CYCLE2_REVIEW_REQUIRED | POOL_DROPPED | INSUFFICIENT_EVIDENCE: Critical evidence remains unresolved or stale |
| 8bd5267274de9f9b | CYCLE2_REVIEW_REQUIRED | POOL_DROPPED | INSUFFICIENT_EVIDENCE: Critical evidence remains unresolved or stale |
