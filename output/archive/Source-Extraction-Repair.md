# Source extraction repair

Confirmed code gaps: the resolver did not open its saved programme URL directly; snippet scope checks prevented fetching other official pages; the 120 KB raw-HTML limit cut the Caen page before admissions sections; language parsing missed English labels for French instruction and minimum French level. Evidence excerpts also truncated late-page claims.

Changes: fetch known official programme pages once and reuse full cached text across fields; fetch official search-result pages before checking full-text scope; keep snippets out of verified evidence; reject generic homepages as programme evidence; bound raw HTML at 1 MB and extracted text at 30,000 characters; discard forms/navigation; preserve claim text; record HTTP/content/scope diagnostics; avoid repeating failed fetches per invocation. Existing redirect and PDF limits remain visible as unresolved evidence.

Validation: mocked page tests cover direct fetch without search, one fetch across fields, homepage rejection, failed-fetch deduplication, actual language-label wording and late-page evidence preservation. Live Caen diagnostic on an in-memory database copy fetched 8,170 characters after the size fix versus 2,495 before. Parser now finds French instruction, French C1 and English B2 in that captured page. It does not invent degree or M1-entry evidence. The old generic track identity remains unresolved. No production programme records, scores or statuses were altered; no paid search calls were made.

See Source-Fetch-Diagnostic.json. The whole queue has not been live revalidated by these targeted checks. A Cycle 2 run is still premature.
