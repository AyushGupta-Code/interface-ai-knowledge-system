# Notes

How the system works, why it makes these choices, and what it does not establish. All values and supporting quotations come from the supplied website snapshots. The implementation uses only Python's standard library and makes no network calls.

## How it works

`build()` returns a knowledge system with the contract's `ingest()`, `answer()`, and `conflicts()` methods. Ingest keeps a separate index for every dated snapshot. Markdown headings provide context; ordinary paragraphs and coherent short lists become passages. Table rows and conservatively recognised `label: value` rate lines produce the same structured facts, with product, tier or term, measure, value, page, and snapshot kept separate.

An answer first selects the newest snapshot on or before the requested date, or the latest snapshot when no date is supplied. It finds relevant pages, then checks their passages for the requested answer shape, product, numeric qualifiers, and measure. Rates must be supported by a rate-bearing column or explicitly labelled rate statement. A percentage describing a financing limit is not an interest rate. Eligible evidence is ranked by source authority, subject relevance, and article publication date. Broad rate lists can include matching products from several tables, with personal/business and introductory/regular rates labelled separately. Equivalent supporting facts on other pages can supply additional citations.

Prose answers use a bounded bundle of supporting passages from the winning page. A matching page title can admit passages for inspection at half the lexical weight of body matches; it does not bypass eligibility checks or page selection. Link requests can return actual labelled destinations whose selected-snapshot target facts match the requested product and qualifiers. The bounded article observations can answer organisation counts and named recognition-program questions with their publication dates. Unsupported requests otherwise return an explicit refusal. A narrowly bounded historical fallback can return older evidence when the selected snapshot contains no supporting evidence at all; it labels the amount as historical, dates and cites the older snapshot, and explicitly says the current value is unconfirmed.

Conflict detection compares the same product, segment, tier or term, and measure. It reports both observed changes over time and disagreements between pages within one snapshot. Related row-level findings can share a readable report, but the competing values retain their row labels. A separate bounded article extractor records organisation-wide branch counts and recognition counts for the same award program. Article publication dates remain distinct from crawl dates.

## Running and configuration

No API keys or third-party dependencies are required. Python 3.11 is the grading target. Copy the supplied snapshot archives into `snapshots_zip/` before evaluating a fresh checkout; the organizer's harness extracts them on the first run. These supplied archives and extracted pages are excluded from the public repository and must not be redistributed.

Run evaluation from the repository root:

```bash
python3 harness/run_eval.py --submission submission --eval eval/public_eval.jsonl
python3 harness/run_eval.py --submission submission --eval dev/paraphrase_eval.jsonl
python3 harness/run_eval.py --submission submission --eval dev/refusal_eval.jsonl
python3 dev/check_conflicts.py
```

The practice fixture uses `--snapshots harness/selftest/snapshots --eval harness/selftest/eval.jsonl --conflicts-gold harness/selftest/conflicts_gold.json`. Evaluation output is generated locally under `results/`. The detailed commands, measured results, retained experiments, and rejected experiments are recorded in `PLAN.md`.

## Decisions

**D1. No LLM at answer time.** Retrieval, parsing, eligibility checks, and formatting use deterministic Python rules. This avoids API keys, network access, model downloads, and runtime dependencies. The tradeoff is weaker interpretation of unfamiliar wording; evaluation includes paraphrases and unsupported requests to make those limitations visible.

**D2. Extract values from snapshots, never from the evaluation key.** Ingest rebuilds the data from the supplied pages. Handwritten rules describe vocabulary, document structure, and evidence requirements; they do not supply rates, fees, counts, or answers keyed to question IDs.

**D3. Retain history.** Older snapshots are indexed separately for historical questions and observed changes. A page's presence in an older snapshot does not establish that its value remains current.

**D4. Select dates from observations.** Without `as_of`, use the newest received snapshot. With `as_of`, use the newest snapshot dated on or before it. A date before the first snapshot refuses. Only when the selected snapshot has no supporting evidence at all may the system look back for the newest eligible older evidence. It must not use fallback to overcome conflicting evidence, a product/tier/measure mismatch, expiration, explicit withdrawal, or supersession. The implementation is deliberately narrower: plausible selected-snapshot subject evidence or any later version of the candidate source page blocks fallback, and promotion, article, calculator and file pages are excluded from fallback. Historical output identifies the source snapshot and says the current amount is unconfirmed. It never crosses the requested date and never turns a historical fallback into a confirmed current conflict resolution.

**D5. Shared parsing and evidence checks.** Both tables and explicitly labelled rate lines feed one fact model. A labelled fact is separated before short-line list grouping so neighboring terms do not become one answer. Page retrieval narrows the search; passage checks establish whether the requested evidence exists. The winning evidence determines the answer format. This is a rule-based interpretation pipeline, not a claim that every question can be understood.

**D6. Prefer authority among eligible evidence.** Rate hubs precede product pages, followed by other/promotion pages, calculators, articles, and files. Page type is determined by the site's established URL rules, with whole-path-segment fallbacks for otherwise unclassified rate, promotion, and calculator URLs. Source rank resolves competing observations; it does not prove that a lower-ranked page is erroneous. Articles remain necessary for facts published only in announcements; publication date helps distinguish newer observations from older retained articles.

**D7. Preserve tiers and scope.** Terms, balances, model years, and personal/business product distinctions identify different facts. A specific request selects the matching facts. An unqualified product-family list can include multiple matching products and tables, labelled and deduplicated by identity. A branch-specific schedule does not establish organisation-wide hours.

**D8. Preserve measures.** APR, APY, dividend rate, and interest rate remain distinct. Answer the requested measure; a generic rate answer labels what the source actually publishes. Different measures for one product are not competing values of the same fact.

**D9. Prefer a refusal over an unsupported substitution.** Rate requests must match an extracted product family, requested term/tier, and supported features. An unfamiliar modifier does not silently select a nearby product; an introductory APR for one card cannot become another card's regular APR. Spelled-out month/year terms are normalised as typed month quantities (three years equals 36 months), while calendar dates are kept separate from product terms and model years. Non-rate questions retain the applicable lexical, answer-shape, and numeric checks. Refusals use no unverified numbers or fabricated sources.

**D10. Report observed Change and Disagreement separately.** A Conflict is different observed values for the same fact, across or within snapshots. A **Change** records observations of that fact at different times. A **Disagreement** records differing page values within the same snapshot and cites both contemporaneous pages. Dates describe when a value was observed; they are not assumed effective dates. Dated article claims are reported as dated observations, without asserting that older claims were accurate or that retained historical articles should have been updated. Current resolutions require current evidence; otherwise the limitation must be explicit. Grouping is for readability and does not make different tiers or measures interchangeable.

## Validation and limits

The organizer's private evaluation and conflict answer key are unavailable. Public and reworded scores are development measurements, and the reworded set was written by us. The local conflict benchmark tests our evidence-backed interpretation, including explicit examples that must not be reported as conflicts. It does not establish the organizer's expected grouping or precision on the private list.

The baseline before this build was public `0.7736`, reworded `0.7284`, must-refuse `17/18`, and local conflict F1 `0.7586`. Final measured scores are public **0.8512**, reworded **0.7943** (answer accuracy **0.8085**, consistency **0.9**), must-refuse **17/18**, practice **1.0000**, and local conflict F1 **0.7586** with resolution accuracy **1.0** and **0/8** conflict negatives failing. No public/reworded stale traps or errors were observed. The public target of 0.85 is met. The final-score gap is **0.0569**, exceeding the 0.05 target; this remains an unmet gate rather than a reason for further wording-specific tuning. The reworded set was written by us and tuned against during development, so it is no longer an independent measure; the gap is reported as measured rather than closed by fitting that set. `PLAN.md` records step-by-step results and finishing checks.

The bounded retrieval round is finished. Remaining limitations include eligibility and contact procedures, unfamiliar prose, branch-specific versus general hours, and the deliberately different VTO reporting-year policy. The J.D. Power unsupported-award test still fails in the legacy prose path. The public certificate-list item with no required values receives zero from the default scorer. The reworded set was used during development and is not an untouched holdout.

Python 3.11 is the target but is not installed in this execution environment. Syntax was checked against the 3.11 grammar; the available runtime is Python 3.14.4. An actual cold Python 3.11 run remains unverified. No third-party dependencies are declared.

A full sixth-snapshot test (every snapshot copied, plus an October snapshot whose rate page changes one 12-month certificate APY) passes 41/41, including the organizer's harness run on that copy with no stale value. It first failed: a list answer could add a product page's old value next to the rate page's new one, and an unqualified question could be answered from the business rate page. Lists now keep one value per fact, the one the most authoritative page states in that snapshot, and a question that doesn't say "business" prefers personal rows (category questions such as "your credit cards" still list both). Python 3.11 remains unverified on this machine (see above).
