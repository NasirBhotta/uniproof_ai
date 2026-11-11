# Incremental Pipeline Implementation

## Review and migration decisions

The pre-change database contained 91 programmes. Cycle 1's CLI called the regression dataset; Cycle 2 reloaded a static shortlist; discovery inserted synthetic eligibility and capacity fields. These commands had no durable processing queues. The existing LangGraph evaluator, deterministic validators, schemas, provider protocol, evidence ledger, cache, Cycle 2 analyzer and historical outputs are retained.

The new `pipeline` package adds SQLite-backed workflow state and small adapters around those components. The integrated discovery CLI runs one bounded discovery round, enqueues only new canonical identities, processes pending Cycle 1 work, reviews saved opportunity vectors, processes only promoted Cycle 2 challengers, updates the working pool, and stops. It never starts a second discovery round.

Migration on a database copy: 91 records preserved; 6 previously completed Cycle 1 survivors, 5 previous Cycle 1 rejections, 8 completed Cycle 2 analyses requiring evidence review, and 72 legacy discovery leads without actual stage results. Zero old records entered the automatic Cycle 1 queue. Repeating migration inserted zero rows. Legacy records without completed-stage provenance remain `LEGACY_REVIEW`; explicitly refresh them if desired. An old Cycle 2 analysis is not labeled VERIFIED merely because it has a score. Its snapshot is preserved and its critical evidence determines pool eligibility.

Backup: `output/incremental-diagnostics/before-pipeline.db`.

## Durable state and recovery

`programme_workflow` stores identity, discovered round, stage statuses/versions/timestamps, pool status, evidence version/freshness, refresh fields/reason, supersession, typed snapshots and last error. `pipeline_events` records validated state transitions. `pipeline_rounds` records per-round costs and improvements. `discovery_frontiers` records actual searched regions, cities, institutions, families and query purposes; unavailable department/track dimensions remain NULL rather than invented.

Queue selection uses state, not all programme rows. Completed stages are not rerun. A portable OS lock serializes stage workers and releases on process death. PROCESSING work returns to PENDING when the next worker starts; completed snapshots remain committed. Failed stages retain evidence gathered before failure and report an error for retry. Canonical identity normalizes case, Unicode and whitespace across institution, programme, track and level while preserving existing programme IDs. Superseded programmes remain in the database.

## Research and evidence

New leads retain identity and source only. Cheap scope checks reject explicit non-public/outside-France/non-computing leads; ambiguous entry/language remains unknown for evidence-backed Cycle 1. Existing LangGraph validates one explicitly supplied candidate at a time through a delta backend. Unknown is not failure; inferred M1 labels do not count as verified entry evidence.

The targeted researcher checks fresh, scoped ledger claims and cached documents, then recent query history, then a provider-neutral cached search. It consumes compact snippets and optionally fetches promising official HTML URLs, bounded to 120 KB with at most 10 KB of cleaned text retained. No raw pages are sent to a model. Conservative phrase parsing leaves semantic ambiguity unresolved. Historical advantages require audited records with official provenance; new statistical parsing requires explicit labels and an unambiguous M1 cohort/year. Unverified legacy benchmark tables cannot drive the incremental pool.

Default bounds: 12 discovery requests, 6 Cycle 1 requests, 6 Cycle 2 requests; 20 pending Cycle 1 candidates, 5 promoted challengers and 5 Cycle 2 candidates per invocation. Each stage uses a shared budget rather than granting the same budget to every programme. These are caps, not mandatory spending. Search errors do not establish incompatibility. LLM calls/tokens are zero in the default deterministic path. Difficult claims remain manual checks rather than fabricated facts.

Field refresh supports language, calendar, historical, degree, structure, prerequisites, route, tuition and stability. Only requested field groups are researched; unrelated evidence survives. Local validators may rerun to reconcile the combined result without extra network/model calls. Changes to target intake, new verified ledger claims and stale retained-pool evidence schedule narrow refreshes. An explicit refresh may bypass the cache for its targeted query only. Provider/budget unavailability leaves refresh work pending.

## Promotion, pool and final selection

Pydantic opportunity vectors compare academic fit, degree, prerequisites, language, historical pressure, candidate position, route complexity, evidence confidence, stability, region and finances. Missing evidence is never a positive advantage. Dominance and diversification govern decisions; a numeric profile score does not decide promotion or replacement. The working pool has a maximum of 15; it is not padded to 10 or 15. Insufficient critical evidence prevents retention. Historical pressure and financial/stability dimensions remain unknown unless supported.

The final stage reads the retained pool, checks freshness and critical evidence, and creates up to seven diverse human comparison options. It performs no broad discovery and never submits applications. If seven credible options do not exist, it reports the shortfall. It does not manufacture probabilities or degree/ECTS equivalences.

True pipeline diminishing returns requires three consecutive rounds with at least three successful actual discovery calls across two or more frontiers, no pool improvement, at least seven credible retained programmes, and actual exploration of at least nine regions. Duplicate/cache-only rounds cannot advance this streak. A bounded low-yield round remains resumable and is not proof of national exhaustion.

## Commands

```powershell
python run_discovery_round.py
python run_discovery_round.py --discovery-only
python run_cycle1.py --pending-only
python run_cycle2.py --pending-only
python run_pool_review.py
python run_final_selection.py
python run_cycle1.py --pending-only --refresh PROGRAMME_ID --fields language
```

Manual stage commands default to pending-only and accept `--db`, `--output-dir`, `--candidate` and `--search-budget`. Existing legacy snapshot functions remain available in their modules, but are not the default command path. `FRANCE_SEARCH_FACTORY=package.module:factory` selects any provider implementing the existing SearchClient contract; Tavily remains the fallback configuration. Providers can also be injected into the service directly.

## Reports

Existing discovery reports retain their structure and append pipeline metrics plus exact programme-level transitions. `Pipeline-Latest.json` contains stage metrics; `Pipeline-Round-NNN.json` retains the complete integrated-round result. Historical Cycle 1/Cycle 2 reports are not overwritten by incremental runs. `Final-Selection.md` is the separate human decision report.

## Tests before controlled execution

80 tests passed, including 19 new incremental tests covering old/new delta isolation, completed-stage reuse, narrow refresh, weak/strong challenger promotion, pool replacement without deletion, canonical idempotency and new tracks at known universities, interrupted/failing-stage recovery, legacy snapshots, unknown-not-fail, historical provenance, and zero-search convergence guards. All five command help interfaces load successfully.

## Known deliberate limits

Legacy discovery leads with synthetic metadata are preserved but not automatically promoted or batch-reprocessed. Conservative deterministic extraction cannot settle every admissions question; unresolved claims stay visible and cannot fill the credible pool. The frontier registry is finite; coverage and exhaustion remain separate. This implementation provides bounded incremental work, not an unattended infinite research loop.


## Completed controlled validation: round 8

Exactly one integrated live discovery round was executed with `python run_discovery_round.py`. No second discovery round was started. The separate final-selection renderer performed no web searches.

| Stage / metric | Observed |
|---|---:|
| New programme/track delta | 6 |
| Existing programmes rerun through Cycle 1 | 0 of 91 |
| Cycle 1 processed / screening passed / rejected | 6 / 6 / 0 |
| New-delta promotions to Cycle 2 | 0 (insufficient evidence) |
| Legacy survivor promoted for its first Cycle 2 analysis | 1 |
| Previously completed Cycle 2 analyses rerun | 0 |
| Cycle 2 processed / verified | 1 / 0 |
| Pool additions / replacements | 0 / 0 |
| Existing records cheaply reviewed during migration | 14 |
| Unchanged/insufficient-evidence pool decisions, including migration | 20 |
| Discovery provider calls | 7 |
| Targeted Cycle 1 / Cycle 2 provider calls | 6 / 4 |
| Total provider calls | 17 |
| Downstream cache hits / searches saved by memory | 4 / 1 |
| Official page fetches | 6 |
| LLM calls / tokens | 0 / 0 |
| Pipeline errors / provider failures | 0 / 0 |
| Discovery budget remaining | 5 of 12 |
| Stop reason | FRONTIERS_DEFERRED |

Screening passed means no established hard incompatibility; it does not mean all eligibility fields are verified. The six new candidates lacked enough evidence to justify promotion. The single Cycle 2 challenger was an existing Cycle 1 survivor that had never completed Cycle 2; its original Cycle 1 snapshot is retained separately. No programme qualified for the credible working pool. Final-Selection.md therefore honestly contains zero finalists, not an invented final seven.

Preservation check: universities 46 -> 46; programmes 91 -> 97; evidence IDs 178 -> 178; search history 68 -> 85; research runs 7 -> 8. Every original ID remains in all five tables. All old Cycle 1/Cycle 2 JSON reports remain available. No pending PROCESSING states or stage errors remain.

Final regression result: **81 passed**, including 20 incremental tests. The additional test verifies that Cycle 2 cannot overwrite the original Cycle 1 snapshot. Round-report rendering is idempotent, so enriching the captured report did not execute any additional work.

Evidence files:
- `output/incremental-diagnostics/controlled-round.log`
- `output/Discovery-Round-008.md` (exact programme-level transitions)
- `output/Pipeline-Round-008.json`
- `output/Pipeline-Latest.json`
- `output/Final-Selection.md`

The integrated pipeline and migration are validated; strong admissions options have not yet been established by this run. Existing uncertainties, unresolved official-source interpretation, and missing critical evidence remain visible for targeted follow-up.
