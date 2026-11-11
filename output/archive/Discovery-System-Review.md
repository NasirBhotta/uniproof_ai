# Discovery System Review

Review date: 2026-10-04. This review was written before changing application code. Baseline source line numbers below refer to the inspected working tree.

## 1. Executive Summary
The historical failure is real: SQLite research_runs/discovery_round_1 records zero external searches, nine duplicate blocks, nine cache hits, and DIMINISHING_RETURNS in summary_markdown. However, the current untracked discovery runner has already been changed: all three diminishing-return assignments require at least three counted searches and two frontiers. The current CLI cannot select that reason with searches_attempted=0. Do not attribute the historical failure to a current branch without the old source.

The controlled unmodified CLI execution produced round 5: REGIONS_SATURATED, five wrapper calls, five actual Tavily calls, five HTTP 200 responses, two new programmes, two universities, budget seven. The provider is configured and reachable. Before execution memory contained 46 universities, 67 programmes, 53 history rows and four runs (not the originally reported 43/51). Backup: discovery-diagnostics/before-review.db. Evidence: discovery-diagnostics/before.log and trace_cli.py. Tracing uses sys.settrace/runpy on the actual CLI, without modifying application code or exposing credentials.

## 2. Exact Root Cause
Historical branch: not recoverable from the available source. The old run is persisted, but round_runner.py is untracked and its current contents already include remedial guards and rewrites. The retained check_semantic_duplicate helper increments BOTH duplicate_queries_blocked and cache_hits for an exact history match; this explains how those two historical metrics can coincide without any disk-cache retrieval, but does not prove the unavailable historical stopping branch.

Confirmed current latent zero-network failure: execute_discovery_round calls CachedSearchClient.search, then unconditionally increments searches_attempted and provider success. A disk hit returns before inner.search. If three cached results yield no new candidates on different frontiers, consecutive_actual_low_value reaches three and line 1485 selects DIMINISHING_RETURNS with zero real provider calls. The invariant checks the same inflated wrapper counter and therefore passes. Regression tests must exercise the runner and cache boundary, not reimplement its condition.

## 3. Runtime Call Path
run_discovery_round.py:main -> discovery/round_runner.py:execute_discovery_round -> memory/database.py:get_connection (schema/migration) -> EfficiencyGovernor(conn) -> profile.load_candidate -> get_default_search_client -> get_next_recommended_regions(top_n=3) -> FRENCH_REGIONAL_CITIES/FRANCE_REGIONS_REGISTRY -> DiscoveryFrontier queue -> programmes ID lookup -> COMPREHENSIVE_FRANCE_CATALOG matching -> persist_programme_candidate for unseen local IDs -> generate_frontier_query -> EfficiencyGovernor.is_exact_duplicate -> check_duplicate_status -> normalize_query + SQLite search_history -> up to five alternative templates -> CachedSearchClient.search -> cache file OR TavilySearchClient.search -> httpx.Client.post -> SearchBatch -> extract_candidates_from_search_results -> EfficiencyGovernor.record_search_result -> persist_programme_candidate -> stopping checks -> seed_regional_coverage -> ResearchRunRepository.record_run -> discovery reporting -> CLI summary.

This CLI is an imperative discovery runner. It does not invoke LangGraph, Cycle 1/2 validators, research/backend.py, SearchHistoryRepository, or EfficiencyGovernor.should_search. Do not invent edges to these components. If DB is missing, import_existing_runs_into_memory is called first.

## 4. File + Function Responsible
round_runner.py:execute_discovery_round lines 1414-1431 count wrapper calls as provider calls; lines 1480-1485 treat no extracted candidates as a failed discovery. search/cache.py:CachedSearchClient.search returns disk data without provider invocation and has no TTL. search/tavily.py:TavilySearchClient.search swallows HTTP/timeout errors into empty successful-looking batches. round_runner.py:extract_candidates_from_search_results reads content although SearchResult defines snippet. The runner calls is_exact_duplicate directly, which does not increment duplicate counters.

## 5. Why Search Provider Is Not Being Called
No such failure in the controlled live baseline: five inner Tavily calls were observed. Current early paths: missing client skips Step B; six recent query variants skip the frontier; disk cache returns before Tavily. The old zero-call run cannot be replayed exactly with the changed source/state. No mock/offline switch or fallback web provider is selected by this CLI.

## 6. Why DIMINISHING_RETURNS Is Triggered
All assignments are in execute_discovery_round: line 1359 before popping the next frontier; line 1485 after results; line 1501 in final fallback. Each requires consecutive_actual_low_value >= configured threshold, searches_attempted >= 3, and at least two distinct attempted frontiers. Duplicates continue before counters; local absence does not increment low value. Cache hits and swallowed provider errors DO increment it through the wrapper path. Line 1509 hard validator requires low value >=3 regardless of a custom threshold (inconsistent for thresholds below three). The baseline triggered neither branch: it exhausted five queued cities, then line 1505 assigned REGIONS_SATURATED without proof of exhaustion.

## 7. Deduplication Review
normalize_query lowercases, removes quote characters, collapses whitespace; it does not remove cities/regions or accents. SQLite uses normalized text (indexed), not a query hash. Disk cache uses SHA256 of raw query + search options. Exact matching checks latest matching query, 30-day timestamp TTL, and optional target institution/purpose. Runner passes only query/TTL, so stored target/programme/field/region/city/purpose/round scope is not consulted. No target-intake/source-freshness TTL exists. Semantic similarity uses >=0.75 token overlap within same region OR city over last 30 rows, without time filtering; the runner ignores that status by checking only EXACT_DUPLICATE. Thus Master Informatique Hauts-de-France does not exact-block Amiens, Lens or Valenciennes. query_effectiveness is empty and unused by this path; SearchHistoryRepository.find_equivalent_search has no TTL but is not called here. Disk cache has no TTL, so history expiry alone cannot refresh actual web evidence.

## 8. EfficiencyGovernor Review
should_search can reuse verified institution evidence, enforce three targeted attempts, and check field weights/confidence. It is NOT called for discovery. Actual discovery gate is query history + runner budget + client availability. Fresh GovernorMetrics and _attempt_counter are created each round. Do not route discovery through institution-wide evidence reuse as though finding one programme resolved all tracks. check_semantic_duplicate conflates duplicate blocks and cache hits; current runner bypasses it, so duplicate metric stays zero despite 11 rewrites in baseline.

## 9. Frontier Planner Review
Current planner takes three regions, not 10+. It then creates all listed city frontiers (five in baseline). Known universities do not exclude cities or tracks. HIGH coverage is separate from PARTIAL exhaustion; only EXHAUSTED is excluded by SQL. One evaluated programme does not exhaust a university: local candidates are filtered by programme hash. However, repeated calls favor the same small regions; once their six variants are all recent, the runner exits without looking at other eligible regions. Queue exhaustion is mislabeled REGIONS_SATURATED. Fallback region filling also ignores exhaustion flags. Region last_searched is overwritten for every region during coverage seeding, so it does not represent actual searches. No proven national exhaustion exists.

## 10. Persistent-State vs Round-State Review
| Value | Initialization and update |
|---|---|
| external_search_calls | GovernorMetrics default zero; record_search_result increments, including wrapper hits/errors in baseline |
| searches_attempted | local zero; increments after each wrapper call, including errors |
| universities_attempted | empty set; only adds universities when candidates persisted, not when unsuccessful searches occur |
| new_candidates_found | length of new_programmes_evaluated, initially empty |
| candidates_deeply_verified | alias for viable_newcomers length; no deep verification actually runs |
| duplicate_queries_blocked | new metric zero; runner never increments |
| cache_hits | new metric zero; cache wrapper has no tracker, so real cache hits are invisible |
| remaining_search_budget | configured max minus searches_attempted; never loaded from history |
| consecutive_low_value_searches | current name consecutive_actual_low_value, local zero; increments on empty extraction, resets on candidates/local viable additions |
| consecutive_searches_without_new_programme | no such variable in current source |
| frontiers_attempted | empty set; region::city added on wrapper calls |

No accidental restoration of round counters was found. History/programmes/coverage persist intentionally. ResearchRunRepository ignores the supplied stop_reason and distinct-frontier/region/city columns, leaving NULL/defaults despite schema support.

## 11. Search Provider Wiring Review
Provider: configured / reachable (five actual HTTP 200 calls). Key: configured; never printed. get_default_search_client reads TAVILY_API_KEY environment then cwd/.env; constructs cached Tavily timeout=30s. No disable flag, offline mode or alternate fallback in this path. Missing/initialization failure returns None and is incorrectly reported as saturation. Injected search_client supported. Raw content is requested by default even though discovery only needs snippets. Tavily catches timeout/HTTP errors and returns empty batch; genuine error becomes apparent success and is cached indefinitely.

## 12. Confirmed Bugs
1. Cache hits counted as external calls/budget consumption/low-value searches.
2. Provider failures counted as successful empty searches and cached.
3. Disk-cache TTL missing despite 30-day history refresh.
4. Duplicate blocks not counted; legacy helper counts them as cache hits.
5. Completed city queue mislabeled exhaustion; repeated top-three planning can starve other regions.
6. Snippet attribute mismatch drops evidence.
7. Universities attempted only counts universities producing new candidates.
8. Existing zero-search regression tests mostly duplicate conditions in test-local variables, not production execution.
9. Stop metadata passed to repository is silently discarded.
10. No deep verification runs, but reports claim deep verification. Extractor/persistence assigns synthetic capacity, prerequisites, public status, degree PASS and viability. These pre-existing evidence-quality problems are separate from search reachability and require a dedicated validator-integration review; do not treat live discovered counts as verified admissions findings.

## 13. Suspected Secondary Bugs
Latest-row-only exact scope matching can miss older matching scope. Region timestamps cannot support fair recency selection. Programme identity is inferred from snippets and frontier identity, potentially misattributing other institutions and M2/private results. Repeated child-table inserts lack uniqueness. Hardcoded verification dates and generic evidence confidence can overstate freshness. These are documented, not grounds to rebuild the pipeline in this patch.

## 14. Minimal Recommended Fixes
Expose cache-hit/error outcome at existing SearchBatch boundary; apply optional 30-day disk TTL for discovery only; never cache provider errors. Count actual attempts separately from successful searches; failures consume request budget but never count toward diminishing returns or successful history. Record duplicate metrics. Select up to three regions with at least one currently actionable query, retaining local candidates; use explicit deferred/unavailable/error stop reasons rather than unsupported exhaustion. Read snippet, request no raw page content, and count universities actually searched. Preserve output layout and all existing memory. Add runner-level regression tests with fake provider and real SQLite/disk cache, then validate real CLI again. Correct deep-verification count to zero for this runner and persist supplied stop metadata. Do not pretend this fixes the separate evidence-validation pipeline.

## 15. Architecture Components That Should NOT Be Changed
LangGraph, SQLite schema/memory, Cycle 1, Cycle 2, SearchClient abstraction, caches, governor, validators and report structure remain. Preserve pre-existing user edits. Never clear history/programmes/cache to force activity. No whole-page LLM requests or architectural replacement.

## Invariant assessment before patch
A/G: syntactic guards pass but wrapper counters allow zero-provider violations. B: duplicates do not increment low value in current runner. C: violated by disk-cache hits. D/E/F: respected for current track/city generation, though final saturation label is unsupported. Budget resets and is checked, but counts the wrong boundary.

## Patch and validation (completed after the review above)

Applied focused changes to the existing runner, governor metrics, SearchBatch/cache/Tavily boundary, run metadata persistence and CLI logging. SearchBatch provenance is excluded from serialized cache payloads. Cache TTL is opt-in (30 days for discovery); existing callers retain their defaults. Recent exact deduplication remains active. Cached results with no new candidates advance to the next of the existing six query dimensions without consuming network budget or raising the low-value counter. No tables, history or caches were cleared.

Region selection now checks the existing ranked regions for available query variants/local candidates, selecting at most three eligible regions. Completed bounded queues return FRONTIERS_DEFERRED rather than claiming regional exhaustion; missing/failed providers have explicit reasons. Failed requests still consume the network-attempt budget; only successful real searches can satisfy diminishing-return guards. The old check_semantic_duplicate helper no longer labels duplicate blocks as cache hits. The snippet mismatch and unnecessary raw-content request were corrected. Deeply verified count is zero because no verification pass runs here. Other candidate-evidence quality issues in section 12 remain outside this search patch.

### Regression validation
`.venv/Scripts/python.exe -m pytest -q`: **61 passed**. Eleven new tests execute real production paths: nine blocked queries with 43 known universities; three duplicates plus entirely cached alternatives with zero low-value increment; three genuine empty provider calls; failed provider responses without cache/history poisoning; unavailable provider; expired history plus expired disk cache; counter reset across rounds; moving beyond a fully recent region; snippet extraction; HTTP 401 propagation without secret content; and region-versus-city query distinction. The existing integration test now injects a deterministic provider to prevent accidental network usage. System `python` is 3.10 and has no pytest; the project virtual environment was used for testing.

### Live CLI validation
Executed the requested `python run_discovery_round.py` after patch. Evidence: [after.log](discovery-diagnostics/after.log), [round 6 report](Discovery-Round-006.md).

| Metric | Observed |
|---|---:|
| Selected regions | 3 |
| City frontiers actually searched | 5 |
| Actual HTTP POSTs to Tavily, all HTTP 200 | 5 |
| Provider attempted / successful | 5 / 5 |
| Duplicate queries blocked / rewrites | 16 / 16 |
| Universities attempted | 5 |
| Newly persisted programme candidates | 15 |
| Deeply verified programmes | 0 |
| Remaining search budget | 7 of 12 |
| Stop reason | FRONTIERS_DEFERRED |

The run used its five selected city frontiers and deferred further expansion to later rounds. The 15 discoveries are provisional parser outputs, not independently verified viable admissions options. No provider exception occurred in either live run; error behavior was verified using a real httpx.HTTPStatusError with HTTP 401 in a controlled test.

Memory preservation check: all original university/programme/search-history/run IDs remain. Counts changed from 46/67/53/4 before review to 46/84/63/6 after the two authorized live runs. Original database backup is retained under discovery-diagnostics/before-review.db. Existing unrelated user edits were not reverted.

### Remaining limits
The historical zero-search stopping branch cannot be identified exactly without its old source revision; the persisted run proves its output only. Current scope remains six query templates per city and a bounded three-region selection, not proof of national exhaustion. Intake-aware TTL, finer scope matching, accurate region-search timestamps, and the provisional evidence/viability issues listed above remain documented follow-up work. If all selected queries exist only in the disk cache but not in SQLite history, a round can legitimately reuse them and defer with zero external calls; it cannot report diminishing returns. No claim of continuous unlimited exploration is made.
