# Execution plan

Fill in each row as the work happens. "Done" needs evidence.

| Phase | What | Done | Evidence |
|---|---|---|---|
| Setup | Unzip the kit, `git init`, run the starter to get a baseline score | YES | Kit unzipped to repo root; `git init` done; CLAUDE.md, `.claude/settings.json` (deny list) and `.gitignore` (secrets) added. `python3 harness/run_eval.py --submission starter --eval eval/public_eval.jsonl` → `final_score 0.093`, 0 stale-trap hits, p95 0.45 s, 705 pages in the latest snapshot. |
| Research | Follow ~5 topics (a rate, a fee, branch hours, a promo, a tiered table) across all 5 snapshots. For each of the 40 public questions, find the page holding the answer and the page holding each Forbidden value. From that, derive: (1) the page-type order for authority-first ranking, (2) whether any Forbidden value is ever a current Tier of the same product, (3) the default Tier per product, (4) the synonym list. Treat the Answer key's must/must-not lists as truth, not its prose (dup-011 prose says 15-year 6.25%; the site says 6.75%). | YES | `python3 dev/research_map.py` (~3 min) mapped all 40 questions; findings in [dev/RESEARCH.md](dev/RESEARCH.md). (1) Page-type order derived: rate hub > product > promo > calculator > article > file, with articles still eligible and ordered by their own publication date. (2) Forbidden values are sometimes current, but only for a *different product* on the same page (Money Market / HSA rows vs Share Savings), never another Tier of the asked product, so D7 holds. (3) Default Tier is not needed, since all Tiers of the asked product are safe. (4) Synonym list in RESEARCH.md §9. Article dates: 530/538 articles have a standalone date line, the other 8 a byline date. Reworded set: `python3 dev/make_paraphrase_eval.py` → "wrote 80 items for 40 public questions"; `run_eval.py --submission starter --eval dev/paraphrase_eval.jsonl` → `final_score 0.1265`. |
| Decide | Settle the open question: LLM or no LLM, and how it runs without an API key | YES | Settled in a grilling session (2026-11-10); decisions D1–D10 in [NOTES.md](NOTES.md#decisions). No LLM, so no API key needed. |
| Build | `solution.py`: one passage index (sentences, list items, table rows with headers) built in `ingest()` with full history; `answer` = pick Snapshot → search → authority first → qualifier check (else Refusal) → format; `conflicts` from table-row facts | IN PROGRESS | **v1** (`submission/solution.py`): `run_eval.py --submission submission --eval eval/public_eval.jsonl` → `final_score 0.4171`, 0 stale-trap hits, consistency 1.0, p95 0.0 s, ingest 14.4 s. Reworded set → `final_score 0.3235` (gap 0.09, over the 0.05 limit). Main misses: heading-only passages win (dup-011/040/073/060); refusal text contains a phone number, which fails "states no number" (all 3 should_refuse); years in date phrases treated as qualifiers (dup-006); answer in a different paragraph of the right page (hours, Galena address, Forbes); generic words like "interest" let an ARM article beat the rate table (dup-009). **Fix 1/5 (refusal text had a phone number):** removed it → public `final_score 0.4481` (should_refuse 0.33, dup-145 now passes), reworded `0.3531`, 0 stale-trap hits; empty question and a date before the first snapshot both refuse with no numbers. dup-147/dup-102 still answer instead of refusing; that is issue 5 (answer shape), not this one. **Fix 3/5 (years in "as of" dates treated as qualifiers):** date phrases masked, model years kept → public `0.4481` (flat: dup-006 now passes, but dup-075 now quotes the "2 min read" line of the right article, a wrong-paragraph miss for v2), reworded `0.3531 → 0.3826`, 0 stale-trap hits. **Fix 4/5 (section-aware passages):** headings become context only; runs of short lines grouped (ending at a heading, table, long paragraph or new bold label); lead-ins ending in ':' join their list; live Open/Closed badges dropped → public `0.4481 → 0.4636`, reworded `0.3826 → 0.3728` (−0.01: the one-stage search does not use the new structure yet), 0 stale-trap hits. **Fix 2+5/5 (v2 search):** Stage A picks pages that are about the question *and* hold an answer of the right shape (%, $, times, address, date, number); Stage B scores passages on those pages by their own words (title at half weight); the question's most specific non-generic word must appear (D9); rate/fee values only from rate, product and promo pages; answers stay within one table; number ranges only cover dollar amounts and years → public `0.4636 → 0.6817` (should_refuse 3/3), reworded `0.3728 → 0.4737`, 0 stale-trap hits, p95 0.02 s. **Gap public − reworded = 0.21**, far over the 0.05 gate: the main problem now. **Conflicts rebuilt (step 1 of the Codex plan):** v2's `conflicts()` reported 195 entries with junk topics and balance tiers of one account counted as contradictions. A conflict is now one *fact* (segment + product + tier/term, compared measure by measure), reported as either a change over time on its reference page or a disagreement between pages in one snapshot; identical-value copies (personal/business certificate, Roth/Traditional IRA) merge into one entry. Our own benchmark (`dev/conflicts_gold.json`: 11 entries with evidence; `dev/conflicts_negative.json`: 6 "not a conflict" cases), scored with the scorer's `score_conflicts`: `python3 dev/check_conflicts.py` → v2: 195 submitted, recall 0.36, precision 0.02, **F1 0.039**, resolution 0.0, 1/6 negatives failed; now: 66 submitted, recall 0.82, precision 0.14, **F1 0.234**, resolution 0.73, 0/6 negatives failed. Misses: branch count and Forbes (article text, not tables). Answers unchanged: public `0.6817`, reworded `0.4737`, 0 stale-trap hits. **Grouped reports (user decision 2026-11-13: precise facts inside, readable reports outside):** fact-level findings of one product and one kind become one report ("Personal Home Loan rates (changed over time)", one value line per row); identical reports for personal and business merge. `python3 dev/check_conflicts.py` → 16 submitted, recall 0.82, precision 0.56, **F1 0.667**, resolution 0.82, 0/6 negatives failed (the negative check now treats only lines of the same row as competing). Public eval unchanged at `0.6817`, 0 stale-trap hits. **Refusal trace (step 2, no thresholds changed):** `answer()` takes an optional `_trace` dict; `python3 dev/trace_refusals.py` (reworded) and `--eval eval/public_eval.jsonl` → 12 wrong refusals (10 reworded, 2 public). 6 stop at the specific-word check with a filler word chosen (between, highest, holding, list, shut, mid); 4 at page selection (no fallback to the next pages; "link/page/list" counted as topic words); 2 at query shape ("change my address"; a yes/no comparison). None at ranking. The step-2 trace report was removed before submission (it is in the git history). Public eval unchanged at `0.6817`. **Refusal fixes (step 3, targeted at the stage that dropped the evidence):** wording words (between, highest, lowest, top, best, list) can't be the specific word; synonyms shut (down)→close, holding→balance, drive-up window→drive-up; "mid/early/late" before a month dropped with the date; answer-kind words (link, page, list, website) no longer count as topic words; if the best-covered pages yield no passing passage, every page with coverage ≥ 0.5 is tried before refusing; "how do I change/update…" is a procedure question, not an address one. Public `0.6817 → 0.7282` (should_refuse still 3/3), reworded `0.4737 → 0.5619` (paraphrase consistency 0.525 → 0.625), 0 stale-trap hits, 0 errors. Wrong refusals 12 → 2 (dup-080-p2 "location finder" isn't site wording; dup-104-p2 is a yes/no comparison). Gap now 0.17. **Labelled rates only:** a % counts as a rate only under a rate/APR/APY/dividend column, or in a sentence naming a rate ("borrow up to 80% of construction costs" is not one). Public unchanged `0.7282`; reworded `0.5619 → 0.5919` (dup-147-p1/p2 now refuse; should_refuse 6/6), 0 stale-trap hits, no other item changed. **Same-fact sources:** a table answer also cites the other rate and product pages that state every quoted row as the same fact in the same snapshot (D10 identity, values equal), up to 5. Public `0.7282 → 0.7398`, reworded `0.5919 → 0.6031` (dup-009/016/017 and their rewordings gain the source credit), 0 stale-trap hits, p95 0.03 s; conflict benchmark unchanged (F1 0.667, 0/6 negatives). **Score and tie fixes (from the full miss trace):** "interest rate(s)" → "rate" (tables say Rate/APR; "interest" only matched prose, so the rate table fell under the cutoff); ranking breaks ties with how much of the question's non-category words the page title names, before article date; "Nth time" counts as a count-shaped answer. Public unchanged `0.7398`; reworded `0.6031 → 0.6327` (dup-011-p2 0 → 1, dup-040-p2 0 → 0.5, dup-034-p2 0.14 → 0.28, dup-094-p2 0 → 0.33; paraphrase consistency 0.625 → 0.70), 0 stale-trap hits, should_refuse 6/6. A first version counted category words ("branch") in the title and broke dup-064-p1; excluded them. Gap now 0.11. **Must-refuse benchmark:** `dev/refusal_eval.jsonl`, 18 questions the site can't answer (made-up products, terms and branches, an intro rate only another card has, a date before the first snapshot...), each checked against the snapshots. Current system: `run_eval.py --eval dev/refusal_eval.jsonl` → 14/18 refused (fails: Rewards Visa intro rate, J.D. Power award, business construction loan rate, interest-only mortgage). **Rejected attempt, structured subject checks (not committed):** names learned from capitalisation on the site must be in the passage; for rate questions, product words (rate-row cells and product page titles) must be in the row, other words on the page, unknown words refuse. Result: public `0.7398 → 0.6855` (dup-147 and dup-076 broke), reworded `0.6327 → 0.6147`, must-refuse still 14/18 (fixed ref-08/16, broke ref-06/07), ingest 40 s → 73 s. Causes: capitalisation marks UI words as names ("Update", "Online Banking"); product words aren't scoped to their product ("purchase" belongs to mortgages, so "regular purchase APR on the Platinum Visa" refused); product words missed table captions ("boat"); and the targeted misses (join, Forbes, student loans, contact details) still fail without the veto, because they stop at page coverage and the score cutoff. Reverted. **Evidence bundle (per-page step):** a prose answer now carries the winning page's other passages that pass every check and score within 0.15 of the winner (same page, page order, up to 3, 900 chars), so an answer split over adjacent paragraphs isn't cut in half; "still visit/open now" questions ask for a date unless they ask where/which branch instead. Public unchanged `0.7398`; reworded `0.6327 → 0.6889` (Hy-Vee date x2, Hy-Vee alternatives, Home$tart amount, mobile wallets now full; credit-card list partly), must-refuse unchanged 14/18 (the one trap hit is ref-08's 2.90%, already failing before), 0 stale-trap hits on public and reworded. **Gap now 0.05** (gate: ≤ 0.05). **Rate questions checked by product family (replaces the one-word veto for rates):** the question's family (from the same patterns the conflict code uses) must have rate rows, and the rate must come from one of them; question words this family's rows use must be in the row; a modifier right before the family name that its rows never use ("reverse", "interest-only", "Unicorn") or a feature only a sibling product has ("introductory" on the Rewards Visa) refuses; "standard/regular/purchase" mean the ordinary rate and are never treated as features; a rate question naming no rate family (construction, payday) refuses; "what APR do you charge" is a rate question, not a fee one. Must-refuse `14/18 → 17/18`; public unchanged `0.7398`; reworded `0.6889 → 0.6903`; 0 stale-trap hits. Left: ref-14 (J.D. Power, a non-rate question). **Non-rate questions, rejected experiment:** checking the specific word on the page instead of the passage → public unchanged, reworded `0.6903 → 0.6759` (dup-064-p2 broke), nothing fixed; reverted. Re-trace (tracer updated for the family check's word list): the non-rate misses still stop at the specific-word check with a verb or qualifier chosen (eligible, received, ranked, took, starting, flexibility, online, phone). Site statistics don't separate these from subjects cleanly: capitalisation fails for *lobby* (0.00) and *update* (0.49); share of heading/label occurrences fails for *ranked* (0.29 vs *join* 0.14). **Second non-rate experiment, branch places (not committed):** only words from the site's own branch picker ("Select a Branch Asbury: Saratoga Rd. … Waterloo: W Mullan Ave.") must be in the passage, and a branch named by a non-place word refuses; all other words only score. Public `0.7398 → 0.7243`, reworded `0.6903 → 0.6608`, must-refuse unchanged 17/18. It broke dup-064-p2 (without the *lobby* veto an unrelated paragraph wins) and dup-068 (the picker glues "SE" onto "Galena"), and fixed none of the targeted misses: with no veto, join / Forbes / student loans / contact details still lose on page coverage and scoring. Reverted. Conclusion: for non-rate questions the veto is not what holds these back; the evidence is not reached (eligibility list shares no question word; contact page under the coverage cutoff). **Lists across tables:** a rate question naming a category (credit cards, home loans) now also takes the family's other rows that score as high as the winner, from rate and product pages, once per fact (D10 identity), up to 12, each page cited; "APRs/APYs" count as rate words. Public `0.7398 → 0.7736`, reworded `0.6903 → 0.7234` (dup-034 and dup-040 full in both sets), must-refuse unchanged 17/18, 0 stale-trap hits, conflict benchmark unchanged. Gap 0.05. **Provider names:** "Apple, Google or Samsung Pay" is written as "Apple Pay, Google Pay or Samsung Pay" in the answer text (coordinated capitalised names before Pay/Wallet only; source quotes keep the site's wording). Public unchanged `0.7736`; reworded `0.7234 → 0.7284` (dup-094-p2 0.33 → 1); must-refuse 17/18; 0 stale-trap hits. **Article-text conflicts:** organisation-wide branch-office counts ("It has … 22 branch office locations", "Dupaco now operates 22 branches"; not a biography's "Dupaco's 18 branches") and "the Nth time <awarder> recognized Dupaco" (kept apart per award program, from the article title) are read from each article's newest snapshot with the article's own date; differing values become one dated report each, resolved to the newest article's value. `python3 dev/check_conflicts.py` → 18 submitted, recall 0.82 → **1.0**, precision 0.61, **F1 0.667 → 0.759**, resolution 1.0, 0/8 negatives failed (2 new negatives: other branch scope, "second time in just a month"). Answers unchanged: public `0.7736`, reworded `0.7284`, must-refuse 17/18.  **Q1–Q4 build execution (2026-11-14):** details and item deltas are recorded below under "Measured build execution". |
| Gates | Public eval ≥ 0.85; 0 stale-trap hits; p95 ≤ 2 s; our own reworded set (`dev/paraphrase_eval.jsonl`) within 0.05 of the public score; fake 6th-Snapshot test (copy of `snapshots/` plus an October Snapshot with one changed rate, run with `--snapshots <copy>`): "current" moves to it and As-of dates still pick the right Snapshot; runs from a fresh clone on Python 3.11 | INCOMPLETE |  See Finishing gate evidence: public target met, gap and Python3.11 runtime outstanding. |
| Submit | `NOTES.md`, `requirements.txt`, push to the public GitHub repo (no snapshots, no API keys), email the repo link and commit to assignments@interface.ai | PENDING | |

**Deviations (declared when they happen, with why):**
- Setup: the Conflicts score (15%) can't be measured locally. The scorer only scores it with `--conflicts-gold`, and that file is in the organizers' private copy. Our local final score covers accuracy, consistency and speed only. We'll need our own check for `conflicts()` in Gates.
- Repo: public, not private. The PDF says private with read access, but interface.ai's email asks for a public repo without the supplied snapshots or API keys. `snapshots_zip/` is gitignored, so a fresh clone needs the kit's zips copied in before the scorer runs. NOTES.md must say so. This replaces the "runs from a fresh clone" gate.

**Decisions agreed in the grilling session of 2026-11-14 (to be built together once every question is settled; second opinions from Codex):**

- **Q1. The organizers' practice test is a finishing gate.** `run_eval.py --snapshots harness/selftest/snapshots --eval harness/selftest/eval.jsonl --conflicts-gold harness/selftest/conflicts_gold.json` scores 0.17 at `4ef2221` (accuracy 0.2, conflicts F1 0.0). Causes (confirmed by Codex): facts come only from table rows, so "label: value" rate lines give no facts and the family check refuses; `page_kind` knows only Dupaco URLs (`/rates/certificates`, `/promo`); conflicts come only from tables; `split_page` merges adjacent "label: value" lines into one passage; "six month **share** certificate" fails on the unknown modifier "share" and on "six" not becoming a number. Fix: one conservative "label: value" parser feeding the existing fact model (answers and conflicts), parsed before short-line grouping; number words normalised; URL-word fallback for page type only on otherwise unclassified paths. Gate: the 4 non-fee questions and the conflict pass; the fee question becomes required with Q2; public, reworded, must-refuse and conflict negatives no worse.
- **Q2. Historical fallback (amends D4).** Search the selected snapshot first. Only when it has no supporting evidence at all (not when evidence conflicts or fails to match the product, tier or measure), answer from the newest earlier snapshot that has it, never crossing the as-of date, excluding expired offers and explicitly withdrawn or superseded facts, citing that snapshot and labelling it as history ("The latest snapshot doesn't publish this fee. It was $2.50 in the 2026-01-05 snapshot; I can't confirm the current amount."). Fallback values never become a current-value resolution in `conflicts()`. Tests: missing page, expired promotion, explicit withdrawal, changed fee, as-of boundaries; existing benchmarks unchanged or better.
- **Q6. Embedding model: last resort only.** A small local embedding model (e.g. all-MiniLM-L6-v2, ~90 MB, no API key) would only help the misses whose evidence shares no words with the question (join, contact details, Forbes awards, student loans, location finder: about 10–15 reworded and 4 public items); it does nothing for current vs stale values, tiers, refusals, conflicts or dates. Costs: new dependencies (none installed here: no numpy, sentence-transformers or onnxruntime; ~100 MB with ONNX, 1–2 GB with PyTorch), model download or a 90 MB file in the repo, unknown install/internet rights at grading, Python 3.11 vs 3.14 here, weaker line-by-line explanation; about 22,000 unique passage texts, so ~1–2 min extra ingest. Decision: try every rule-based fix first; only if those leave clear gains on the table, run a throwaway experiment in a separate environment (extra ranking signal only, all rule checks kept), keep it only if it gains ≥ 0.03 with no refusal broken, and record it as an amendment to D1.
- **Q3. Conflict kinds: Change and Disagreement, reported separately.** Both stay Conflicts (contract: "across or within snapshots"). Not merged: Codex's in-memory test merged reports by product, F1 0.759 → 0.818 but resolution 1.0 → 0.727, conflict pillar (0.7 F1 + 0.3 resolution) 0.831 → 0.791. Wording states observations, never effective dates: "6.125% on 2026-05-12; 6.375% on 2026-06-09"; "on 2026-09-28 /rates shows 7.29%, /homebuying-guidance shows 6.037%"; article reports are dated observations ("the newest article found, 2026-05-05, says 22; older articles say 23, 24"), not claims that old articles were accurate or that a page should have been updated. Fixes: drop "older values are not contradictions"; a Disagreement cites both pages from the same snapshot in which it was seen; page rank sets the resolution but the reason doesn't blame the lower-ranked page (Business Share Savings: the product page held the corrected 0.15% while the rates hub showed a 0.20% dividend next to a 0.15% APY).
- **Q4. One bounded retrieval round, then finishing gates.** Three mechanisms, each built and measured separately from Q1–Q3 so a regression is attributable: (1) title-based candidate entry: a page whose title matches lets its passages be inspected, never makes them answers, every existing check still applies, and it can't rescue a page already cut at page coverage; (2) labelled link answers for "where can I find…" questions: the link whose label/section names the thing asked, not surrounding prose; (3) the article facts already extracted for conflicts (branch count, recognition count) answer the matching questions, with entity, program, date and source. Codex corrections to our diagnosis: dup-081's real eligibility list already carries "eligible/join" (the tracer pointed at a "Local Service" paragraph); Forbes is lost first at page coverage (0.65 < 0.75) then at the veto; the dedicated student-loan page loses to mortgage pages; dup-008 currently returns personal-loan prose; dup-064/066 keys also accept /contact or a branch article, but /contact's 8:30–5:30 are message-reply hours, so it must not be cited for lobby hours; the tracer's "contains the expected value" evidence is not proof. Expectation: public 0.80–0.85 (ceiling if every fix were perfect: 0.94). Then stop tuning to individual questions. Extra finishing gates: an untouched question set (10–15 questions written by the user without looking at the public set, answers checked against the snapshots, used once and never tuned on); the fake 6th snapshot is a full copy with one changed fact; as-of boundaries (before the first snapshot, exactly on a snapshot date, between, after the last); ingest after answering and calling conflicts() refreshes caches; identical answers across PYTHONHASHSEED values (equal-IDF ties in the specific-word choice currently depend on set order); cold offline Python 3.11 run; conflict provenance per Q2/Q3. If the final public score is below 0.85, record it in PLAN.md and NOTES.md as a deliberate relaxation of the definition of done, with reasons.
- **Q5. GLOSSARY.md stays out of the public repo (user decision).** It remains a local working document. Before the final push: NOTES.md must stand alone (no link to GLOSSARY.md; the few terms it needs, such as Current value, Stale value, Refusal, Conflict, Change and Disagreement, defined inline); GLOSSARY.md removed from tracking and gitignored. GLOSSARY.md is already in the git history (first added in an early commit), so deleting it in a last commit is not enough: the pushed history must not contain it (e.g. push a cleaned or squashed history). How to do that is decided at the Submit step.

## Measured build execution

All five commands run after each step through `python3 dev/run_build_checks.py STEP --previous PREVIOUS`, with `PYTHONHASHSEED=0`, bytecode disabled, and separate ignored `results/build/STEP/` reports:

- `python3 harness/run_eval.py --submission submission --eval eval/public_eval.jsonl --out results/build/STEP/public`
- `python3 harness/run_eval.py --submission submission --eval dev/paraphrase_eval.jsonl --out results/build/STEP/reworded`
- `python3 harness/run_eval.py --submission submission --eval dev/refusal_eval.jsonl --out results/build/STEP/refusal`
- `python3 harness/run_eval.py --submission submission --snapshots harness/selftest/snapshots --eval harness/selftest/eval.jsonl --conflicts-gold harness/selftest/conflicts_gold.json --out results/build/STEP/practice`
- `python3 dev/check_conflicts.py` (stdout retained in `results/build/STEP/conflicts.log`).

Local reports contain supplied text and are not committed. Baseline reproduced: public 0.7736, reworded 0.7284, must-refuse 17/18, practice 0.1700, conflicts F1 0.7586, resolution 1.0, negatives 0/8, zero stale traps and errors.

### Rejected initial variant (`q1`)

Spelled-out year terms became unitless numbers: three-year personal loan rejected a 36-month row. No threshold changes; term qualifiers were corrected to carry units before retaining Q1.

Public / reworded / must-refuse / practice / conflict F1: 0.7736 / 0.7171 / 17/18 / 0.83 / 0.7586. Conflict negatives 0/8; all sets zero stale traps/errors and no newly answered refusal.

Changed item scores: {"reworded": {"dup-028-p2": [1.0, 0.0]}, "practice": {"t1": [0.0, 1.0], "t2": [0.0, 1.0], "t1b": [0.0, 1.0]}}.

Command: `python3 dev/run_build_checks.py q1 --previous baseline`. Trace: `PYTHONHASHSEED=0 python3 dev/trace_refusals.py --all` (output in ignored q1/trace.log).

### Kept Q1 (`q1_units`)

Explicit month/year terms now compare in months using a typed numeric qualifier; a term cannot match a balance or percentage. Four non-fee practice items and its conflict pass. Independent read-only review found no blocking issues.

Public / reworded / must-refuse / practice / conflict F1: 0.7736 / 0.73 / 17/18 / 0.83 / 0.7586. Conflict negatives 0/8; all sets zero stale traps/errors and no newly answered refusal.

Changed item scores: {"practice": {"t1": [0.0, 1.0], "t2": [0.0, 1.0], "t1b": [0.0, 1.0]}}.

Command: `python3 dev/run_build_checks.py q1_units --previous baseline`. Per-item scores unchanged on Dupaco; reworded final increased through consistency, not correctness.

### Rejected Q2 display variant (`q2`)

Historical fallback passed practice, but changing normal current answers to dated display reduced paraphrase consistency and final score. Restore existing current-answer display; keep dates only for explicit as-of and fallback answers.

Command: `python3 dev/run_build_checks.py q2 --previous q1_units` (all five checks listed above).

Public / reworded / must-refuse / practice / conflict F1: 0.7736 / 0.7284 / 17/18 / 1.0 / 0.7586; resolution 1.0; conflict negatives 0/8.

Changed item scores: {"practice": {"t3": [0.0, 1.0]}}.

Stale hits / errors: {"public": [0, 0], "reworded": [0, 0], "refusal": [0, 0], "practice": [0, 0]}. Newly answered refusals: {}.

### Rejected Q2 incomplete guard (`q2_final`)

All five scored benchmarks passed, but independent synthetic review found a withdrawal at a different URL could resurrect an older rate because page coverage was shape-filtered. Add subject-presence checks independent of answer shape; do not retain until the new withdrawal fixture passes.

Command: `python3 dev/run_build_checks.py q2_final --previous q1_units` (all five checks listed above).

Public / reworded / must-refuse / practice / conflict F1: 0.7736 / 0.73 / 17/18 / 1.0 / 0.7586; resolution 1.0; conflict negatives 0/8.

Changed item scores: {"practice": {"t3": [0.0, 1.0]}}.

Stale hits / errors: {"public": [0, 0], "reworded": [0, 0], "refusal": [0, 0], "practice": [0, 0]}. Newly answered refusals: {}.

### Superseded Q2 guard checkpoint (`q2_safe`)

Shape-independent subject guard added; five checks passed. Subsequently broadened explicit expiry vocabulary and added family-level withdrawal protection.

Command: `python3 dev/run_build_checks.py q2_safe --previous q1_units` (all five checks listed above).

Public / reworded / must-refuse / practice / conflict F1: 0.7736 / 0.73 / 17/18 / 1.0 / 0.7586; resolution 1.0; conflict negatives 0/8.

Changed item scores: {"practice": {"t3": [0.0, 1.0]}}.

Stale hits / errors: {"public": [0, 0], "reworded": [0, 0], "refusal": [0, 0], "practice": [0, 0]}. Newly answered refusals: {}.

### Superseded Q2 expiry checkpoint (`q2_expiry`)

Explicit validity and expiry language excludes historical offers; five checks passed. Final version also blocks family-level withdrawal notices and removes missing-current conflict resolutions.

Command: `python3 dev/run_build_checks.py q2_expiry --previous q1_units` (all five checks listed above).

Public / reworded / must-refuse / practice / conflict F1: 0.7736 / 0.73 / 17/18 / 1.0 / 0.7586; resolution 1.0; conflict negatives 0/8.

Changed item scores: {"practice": {"t3": [0.0, 1.0]}}.

Stale hits / errors: {"public": [0, 0], "reworded": [0, 0], "refusal": [0, 0], "practice": [0, 0]}. Newly answered refusals: {}.

### Superseded Q2 withdrawal checkpoint (`q2_kept`)

Five checks passed; final Q2 also removes current resolutions for facts absent from the latest snapshot.

Command: `python3 dev/run_build_checks.py q2_kept --previous q1_units` (all five checks listed above).

Public / reworded / must-refuse / practice / conflict F1: 0.7736 / 0.73 / 17/18 / 1.0 / 0.7586; resolution 1.0; conflict negatives 0/8.

Changed item scores: {"practice": {"t3": [0.0, 1.0]}}.

Stale hits / errors: {"public": [0, 0], "reworded": [0, 0], "refusal": [0, 0], "practice": [0, 0]}. Newly answered refusals: {}.

### Kept Q2 (`q2_complete`)

All19 synthetic cases pass, including different-URL withdrawal, expired offer, changed fee, date boundaries, missing current fact has no current resolution, and ingest cache refresh. Independent review passed. Only practice t3 score changed; current Dupaco answers preserve existing display.

Command: `python3 dev/run_build_checks.py q2_complete --previous q1_units` (all five checks listed above).

Public / reworded / must-refuse / practice / conflict F1: 0.7736 / 0.73 / 17/18 / 1.0 / 0.7586; resolution 1.0; conflict negatives 0/8.

Changed item scores: {"practice": {"t3": [0.0, 1.0]}}.

Stale hits / errors: {"public": [0, 0], "reworded": [0, 0], "refusal": [0, 0], "practice": [0, 0]}. Newly answered refusals: {}.

### Kept Q3 (`q3`)

Observational Change and Disagreement remain separate. Both contemporaneous pages are cited; neither is blamed by rank. Article sources retain actual snapshot IDs. All23 synthetic cases pass; independent review passed. No item score changed. Refusal final0.9403 versus0.9444 is timing-only under simultaneous trace loads (same17/18 correctness); see speed report. This is not a new answered refusal.

Command: `python3 dev/run_build_checks.py q3 --previous q2_complete` (all five checks listed above).

Public / reworded / must-refuse / practice / conflict F1: 0.7736 / 0.73 / 17/18 / 1.0 / 0.7586; resolution 1.0; conflict negatives 0/8.

Changed item scores: {}.

Stale hits / errors: {"public": [0, 0], "reworded": [0, 0], "refusal": [0, 0], "practice": [0, 0]}. Newly answered refusals: {}.

### Kept Q4a (`q4a`)

Title matches now admit passages for inspection, with all existing checks and half-weight title evidence retained. No item scores changed on any set; this mechanism alone does not solve page filtering or intent matching. Independent review passed. Refusal17/18 unchanged; slight final variation is first-query timing under concurrent checks.

Command: `python3 dev/run_build_checks.py q4a --previous q3` (all five checks listed above).

Public / reworded / must-refuse / practice / conflict F1: 0.7736 / 0.73 / 17/18 / 1.0 / 0.7586; resolution 1.0; conflict negatives 0/8.

Changed item scores: {}.

Stale hits / errors: {"public": [0, 0], "reworded": [0, 0], "refusal": [0, 0], "practice": [0, 0]}. Newly answered refusals: {}.

### Rejected Q4b guard variant (`q4b`)

Scored benchmarks improved (certificate link and its rewordings), but independent synthetic review found rate-link requests could bypass unknown modifiers and jumbo/regular distinctions. Reuse family modifier/sibling/required-word checks for linked targets before retaining.

Command: `python3 dev/run_build_checks.py q4b --previous q4a` (all five checks listed above).

Public / reworded / must-refuse / practice / conflict F1: 0.7969 / 0.7528 / 17/18 / 1.0 / 0.7586; resolution 1.0; conflict negatives 0/8.

Changed item scores: {"public": {"dup-008": [0.0, 1.0]}, "reworded": {"dup-008-p1": [0.0, 1.0], "dup-008-p2": [0.0, 1.0]}}.

Stale hits / errors: {"public": [0, 0], "reworded": [0, 0], "refusal": [0, 0], "practice": [0, 0]}. Newly answered refusals: {}.

### Superseded Q4b feature checkpoint (`q4b_safe`)

Family feature/modifier checks fixed unsupported link requests; scored checks passed. Added structural personal/business target scope before retaining.

Command: `python3 dev/run_build_checks.py q4b_safe --previous q4a` (all five checks listed above).

Public / reworded / must-refuse / practice / conflict F1: 0.7969 / 0.7528 / 17/18 / 1.0 / 0.7586; resolution 1.0; conflict negatives 0/8.

Changed item scores: {"public": {"dup-008": [0.0, 1.0]}, "reworded": {"dup-008-p1": [0.0, 1.0], "dup-008-p2": [0.0, 1.0]}}.

Stale hits / errors: {"public": [0, 0], "reworded": [0, 0], "refusal": [0, 0], "practice": [0, 0]}. Newly answered refusals: {}.

### Kept Q4b (`q4b_scope`)

Published links use actual labels/section context and verified target facts. Family, term, feature, unknown modifier and explicit personal/business scope checks retained. All29 synthetic cases pass. Public certificate link and its two rewordings improve0to1; no other item score changes. Refusal17/18 unchanged; final refusal aggregate has small timing variation.

Command: `python3 dev/run_build_checks.py q4b_scope --previous q4a` (all five checks listed above).

Public / reworded / must-refuse / practice / conflict F1: 0.7969 / 0.7528 / 17/18 / 1.0 / 0.7586; resolution 1.0; conflict negatives 0/8.

Changed item scores: {"public": {"dup-008": [0.0, 1.0]}, "reworded": {"dup-008-p1": [0.0, 1.0], "dup-008-p2": [0.0, 1.0]}}.

Stale hits / errors: {"public": [0, 0], "reworded": [0, 0], "refusal": [0, 0], "practice": [0, 0]}. Newly answered refusals: {}.

### Kept Q4c (`q4c`)

Article observations now support answers only for matching organization-count or named recognition predicates, using selected-snapshot evidence and dated sources.36/36 synthetic cases pass; independent review passed. Public reaches0.8512; reworded0.7943. Public-reworded final-score gap0.0569 exceeds0.05: record the gate failure and stop tuning rather than add wording-specific rules. Must-refuse17/18 unchanged.

Command: `python3 dev/run_build_checks.py q4c --previous q4b_scope` (all five checks listed above).

Public / reworded / must-refuse / practice / conflict F1: 0.8512 / 0.7943 / 17/18 / 1.0 / 0.7586; resolution 1.0; conflict negatives 0/8.

Changed item scores: {"public": {"dup-073": [0.0, 1.0], "dup-087": [0.0, 1.0]}, "reworded": {"dup-073-p2": [0.0, 1.0], "dup-087-p1": [0.0, 1.0], "dup-087-p2": [0.0, 1.0]}}.

Stale hits / errors: {"public": [0, 0], "reworded": [0, 0], "refusal": [0, 0], "practice": [0, 0]}. Newly answered refusals: {}.

### Kept determinism fix (`deterministic`)

Explicit lexical anchor ties, sorted lexical score accumulation, and date/URL article ties preserve all per-item scores. Independent review passed. `python3 dev/check_finishing_gates.py --determinism` passes37/37: all public/reworded/refusal answers, sources and conflict reports have identical SHA256864cf1291f011cfb35148b1b2c3ff808a92157c1a11d4cb43e196787db1fde81 across PYTHONHASHSEED0,1,42. Refusal17/18 unchanged; timing-only final variation is recorded in reports.

Command: `python3 dev/run_build_checks.py deterministic --previous q4c` (all five checks listed above).

Public / reworded / must-refuse / practice / conflict F1: 0.8512 / 0.7943 / 17/18 / 1.0 / 0.7586; resolution 1.0; conflict negatives 0/8.

Changed item scores: {}.

Stale hits / errors: {"public": [0, 0], "reworded": [0, 0], "refusal": [0, 0], "practice": [0, 0]}. Newly answered refusals: {}.

## Finishing gate evidence (2026-11-14)

- All seven code steps retained after their scored checks and independent review; exploratory guard variants are recorded above. No organizer files changed; no dependencies/models introduced; no push.
- Public **0.8512** meets0.85. Reworded final **0.7943** (QA0.8085, consistency0.9), so the final-score gap **0.0569** misses0.05. No more tuning is authorized in this bounded round.
- Must-refuse **17/18**; remaining failure is J.D.Power. `env -i PATH=/usr/bin:/bin PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -S harness/run_eval.py --submission submission --eval dev/refusal_eval.jsonl --out results/build/cold-refusal` gives final/QA0.9444,0errors,0traps,p951.70s. This serial cold check resolves aggregate timing artifacts in concurrent step runs; no question changed correctness.
- Practice final **1.0000**,5/5 questions, conflict F1/resolution1.0,0errors/traps. Local Dupaco conflict benchmark F1 **0.7586**,18submitted,11matched,resolution1.0,negatives0/8.
- `python3 dev/check_finishing_gates.py` passes **36/36** synthetic date, fallback, cache, provenance, parsing, title, link and article checks. Fixtures are invented development cases, not a holdout.
- `python3 dev/check_finishing_gates.py --determinism` passes **37/37**, including identical all-set answer/source/conflict digests across seeds0,1,42. Digest864cf1291f011cfb35148b1b2c3ff808a92157c1a11d4cb43e196787db1fde81.
- Full sixth-snapshot direct checks passed40/40. The stricter actual-harness gate FAILS:40/41 checks, synthetic final0.575,1stale trap,0errors. Current item0.15, historicalitem1.0. Current output includes legitimate Business3.40% plus Personal/rates4.44% AND stale Personal/product3.40% for the same fact. The unqualified trap also penalizes the distinct business scope, but the same-personal-identity duplication is a genuine bug. Preserve this failure; no extra tuning beyond the agreed bounded round.
- Actual Python3.11 runtime is unavailable (`command -v python3.11` exits1). `ast.parse(..., feature_version=(3,11))` passes for solution.py; this is syntax validation, not a Python3.11 runtime pass. Available interpreter Python3.14.4.
- Final traces: `PYTHONHASHSEED=0 python3 dev/trace_refusals.py --all --eval eval/public_eval.jsonl` and `PYTHONHASHSEED=0 python3 dev/trace_refusals.py --all`, stored under ignored `results/build/deterministic/`. The tracer finds possible evidence by answer values; its numeric hits are not proof of fact identity.

Implementation commits: Q1 `b31ee8b`; Q2 `5f751bc`; Q3 `9db570d`; Q4a `40ec396`; Q4b `fe88773`; Q4c `952e65c`; determinism `a54a3b4`.


### Final cold checkout and unresolved gates

A fresh `git clone --no-hardlinks` of the committed implementation to a task-created /tmp directory, with the supplied local archive directory made available, ran with an empty environment and `python3 -S` (no site packages/API keys): practice **1.0000**,public **0.8512**,0errors/traps,p95public **0.23s**. Logs: `results/build/cold-clone-practice.log`, `cold-clone-public.log`. The available interpreter is3.14.4; this does not pass the actual3.11 runtime gate. Temporary clone removed after verification.

Outstanding: final-score gap0.0569>0.05; strict sixth-snapshot stale-copy gate fails; actual Python3.11 run unavailable; J.D.Power must-refuse remains failed. Public0.85 target is met, so no relaxation of that target is needed. The stricter mutation exposes existing broad-list assembly using `(fact identity, values)` for deduplication, which retains conflicting copies of one fact instead of resolving to the authoritative value first. This contradicts the intended D6/D7 authority guarantee for family lists. It requires a separately authorized general fact-resolution fix, not another public-wording tweak.

No source code changed after the final five-suite/determinism validation. Final reviewer found no remaining issues within the agreed diffs; the mutation gate is a newly documented system limitation. No untouched set created or used; system-design figure unchanged; no pushes.

**Verification and fixes after the Codex build (2026-11-14):** re-ran every check at `ce9a0e5`: public 0.8512, reworded 0.7943, must-refuse 17/18, practice 1.0 (conflict F1 1.0), conflict benchmark F1 0.759 / resolution 1.0 / 0/8 negatives, 0 stale traps; Codex's numbers hold. Found a speed risk: must-refuse p95 1.66 s (Unicorn Savings 1.6 s, location finder 1.0 s) because the fallback guard ran 18 family patterns over all 120,400 passages and the link index was rebuilt per call over all passages.
- `52e4390` perf: scan only the selected snapshot's passages, cheap checks first, link/fact/family lookups built at the end of ingest. Answers byte-identical on all three sets; p95 public 0.04 s, reworded 0.03 s, must-refuse 0.15 s (max 0.15 s); `dev/check_finishing_gates.py` 36/36.
- `39b3510` fix: list answers keep one value per fact, the one the most authoritative page states in that snapshot (was deduplicated by fact *and* value, so a product page's old 3.40% sat next to the rate page's new 4.44%); a question that doesn't say "business" ranks personal rows first and only category questions (several families, e.g. credit cards) add the other segment. `python3 dev/check_finishing_gates.py --sixth` → 41/41, harness run on the full October copy final 1.0, 0 stale traps. Scores unchanged (public 0.8512, reworded 0.7943, must-refuse 17/18, practice 1.0, conflicts F1 0.759, 0/8 negatives); 21 answers now lead with the personal /rates row instead of /business-rates, same scores.
- Gap public − reworded 0.0569 (> 0.05): recorded as a known limitation, not closed by tuning; the reworded set is no longer independent. Python 3.11 still unverified (no 3.11, uv, pyenv or docker on this machine).

## Refinement round 2 (2026-11-15): three general mechanisms from Codex's review

Codex diagnosed the remaining public misses and prototyped eight variants in scratch copies (no repo changes); I re-ran its three recommended prototypes through `harness/run_eval.py` and got its numbers (0.8667, 0.8667, 0.8512, 0 stale traps). Built with changes, in this order, each checked with `python3 dev/run_build_checks.py STEP --previous PREV` (public, reworded, must-refuse, practice, conflict benchmark) and `python3 dev/check_finishing_gates.py --sixth`. Baseline `base-4ffe17c`: public 0.8512, reworded 0.7943, must-refuse 17/18.

| Step | Commit | Public | Reworded | Must-refuse | Changed items |
|---|---|---|---|---|---|
| Award guard | `4428a4d` | 0.8512 | 0.7943 | **18/18** | ref-14 0 → 1 |
| Support line | `14364b1` | **0.8667** | **0.8113** | 18/18 | dup-060, -p1, -p2 0 → 1 |
| Schedule comparison | `4e81b2a` | **0.8822** | **0.8361** | 18/18 | dup-104 0.5 → 1, -p1 0.5 → 1, -p2 0 → 1 |

Every step: practice 1.0, conflict F1 0.759 / resolution 1.0 / 0/8 negatives, 0 stale traps, 0 errors, no other item changed, sixth-snapshot gate 41/41, p95 ≤ 0.17 s. Gap public − reworded is now **0.0461** (≤ 0.05), with the caveat that the reworded set is not independent.

- **Award guard.** "J.D. Power" tokenised to `power`, so a scholarship article about "the power of education" answered. A question asking about an award (award, recognized, ranked, won…) that names an organisation written with initials now needs a sentence naming that organisation with an award verb. Narrow by design: dotted names only. Forbes answers byte-identical.
- **Support line.** "How do I change / update / correct… ?" with no product-page answer (search refuses, or only a blog post or calculator matches) now says the site doesn't describe the steps and gives the general number: the phone number printed on the most pages of the snapshot, quoted from a contact / help / service page that says "call" or "phone". Change from Codex's prototype: it ran before normal search (so real steps on the site would be hidden) and took the number from the *shortest* passage on any such page (could pick a partner's number). Also dropped web-form country pickers ("Afghanistan +93 · Albania +355…", ≥ 4 dialing codes) at ingest: one was winning dup-060-p1 from a product page.
- **Schedule comparison.** "Do all branches keep the same lobby hours?" (a sameness word + an hours word + a many-places word) lists each distinct published lobby or drive-up schedule, newest first, with the branch announcement and its date, and says to check your branch. Answers only when two or more schedules differ. Changes from Codex's prototype: its trigger needed every question word on a hand-made list (including "keep", "assume", "another"), schedules were listed in text order (a 2021 schedule first), lobby only, and it scanned every passage per question; now a general trigger, newest first, drive-up too, index built at ingest.

**Codex's 24 new rewrites** (not independent): procedure 2/3 (Codex's prototype 3/3: "How should I amend the contact details…" is answered by a Scholarships passage, "authority to amend", because a product page beats the fallback), comparison 3/3, unsupported award 3/3; eligibility, lobby, drive-up and supported-Forbes rewrites still 0/3, as at baseline.

**Rejected in Codex's review:** whole-page anchor context (reworded 0.7796); first H1 as title plus page-local cutoff (public 0.8744, but its student-loan "gain" was housing advice from an article whose title says "student"); derivational morphology (no score change); canonical-hours citations (no honest source to substitute). dup-081 (who can join) stays unsolved: the states are in the service-area text, not the eligibility rules, and conflating the two would be wrong.

## Untouched test set (2026-11-15)

Written by a fresh Codex session that was told not to open submission/, dev/, PLAN.md, NOTES.md or results/, and not to run the system: 36 questions (4 per category; 18 rewordings of public questions, 14 new, 4 refusals; 6 paraphrase groups; 4 historical as_of). Kept local only (`.git/info/exclude`): `dev/untouched_eval.jsonl`, evidence in `dev/untouched_evidence.md`.

Seal: `sha256sum dev/untouched_eval.jsonl` → `d277a765cc3bdf13427f5b963254b80f8111aa5e72173ba566b3f61a80f07ed6`, recorded before the run. Key check without running the system: every must_include value is in the snapshot the question's date selects (scorer's `contains()`) and on the expected source page; no must_not_include value overlaps the key; spot-checked refusals 33 (7/1 ARM rate) and 35 (Mullan Saturday hours) are not stated in the snapshots. Run once at solution commit `ad7587f`; no fixes after it.

**Result of the one run** (`python3 harness/run_eval.py --submission submission --eval dev/untouched_eval.jsonl --out results/untouched`): final **0.3857**, accuracy 0.3974, paraphrase consistency 0.67, repeat consistency 1.0, p95 0.02 s, 0 stale traps, 0 errors. By category: should_refuse 1.00, tier 0.64, temporal 0.50, list 0.29, branch 0.25, conflict 0.25, entity 0.21, current_value 0.04, stale_trap 0.00 (all four refused, none answered stale). 20 of the 32 answerable questions were refused.

Diagnosis only (`python3 dev/trace_refusals.py --eval dev/untouched_eval.jsonl`), no code changed: the refusals come from conversational wording. In 11 of 20 the specific-word rule (D9) picked a filler word the site doesn't use near the answer ("stopping", "arrived", "digit", "profile", "counting", "spell", "mentioned", "published", "shown", "combination", "waiver"); most of the rest fail page coverage because filler words ("navigate", "rely", "budgeting", "spreading") dilute it; one reads "closing bill" as a date question. This is the weakness the step-2 refusal trace found; the earlier fixes removed the filler words seen in our own sets, not the mechanism. The set is now spent: any fix made after reading these results is tuned to it, and would need a new untouched set to measure.

## Chatty-question fixes (2026-11-15), after the untouched result

The untouched result showed conversational wording as the main weakness. To fix the mechanism without tuning to that spent set, two development sets made mechanically from the public questions (same answer keys, only padding added; `python3 dev/make_chatty_eval.py`): `dev/chatty_eval.jsonl` (80: a sentence before or after the question, e.g. "My spouse and I were chatting about this over dinner. … Thanks so much!") and `dev/inline_eval.jsonl` (40: padding inside the question sentence, e.g. "…, roughly speaking, in plain terms?"). Both are tuned against, not holdouts.

| Step | Commit | Public | Reworded | Must-refuse | Chatty | Inline |
|---|---|---|---|---|---|---|
| Before | `4e81b2a` | 0.8822 | 0.8361 | 18/18 | 0.3215 | 0.5039 |
| Read the asked sentence | `3260f07` | 0.8822 | 0.8361 | 18/18 | **0.8434** | 0.5039 |
| Coverage 0.4, specific-word retries | `b50a098` | 0.8822 | 0.8361 | 18/18 | 0.8434 | **0.6155** |

Each step: no public, reworded or must-refuse item changed; practice 1.0; conflicts F1 0.759 / 0/8 negatives; 0 stale traps; `check_finishing_gates.py` 36/36, `--sixth` 41/41, `--determinism` 37/37; p95 ≤ 0.24 s.

- **Read the asked sentence** (`focus_question`). In a message of several sentences where some end with "?", only those are the question; a lead-in before a colon or ", but" is dropped. The other sentences keep only their capitalised names ("I'm stopping at the Peosta branch. What's its address?" keeps Peosta), and qualifier numbers are read from the whole message. Initials ("J.D.") and "a.m."/"p.m." don't end a sentence; a question with no content word of its own ("… How?") keeps the whole message. First version split "J.D. Power" and broke ref-14, and read "How?" alone and broke dup-060-p2; both fixed before commit.
- **Coverage 0.5 → 0.4.** Swept 0.5 / 0.4 / 0.3: inline 0.50 → 0.60 at 0.4, identical at 0.3, nothing else changed. Must-refuse questions are refused by the specific word and the family checks, not by coverage.
- **Specific-word retries (2).** When the rarest word empties the candidates, try the next-rarest, at most twice; a capitalised name is never dropped. Swept 0 / 1 / 2: inline 0.60 / 0.60 / 0.6155.

**Rejected:** dropping question words absent from the 5–20 best-covered pages (chatty only 0.32 → 0.38; dropped "Mullan" and broke ref-04, ref-12, dup-102); restricting the specific word to words on the best-covered pages (public 0.8822 → 0.8512, must-refuse 18 → 16, fixed nothing); separating filler from subject words by page titles or headings (no clean split: "routing", "lobby", "Mullan" are absent from titles while "profile", "asking", "household" are in blog headings).

**Not fixed:** filler inside the question sentence still costs inline 0.27 against public. The specific word is still often a filler word ("asking", "wondering") when other candidates survive, and passage scores are diluted by filler. Separating subject words from conversational words reliably needs a language model or word embeddings, which D1 and Q6 rule out for this submission.

## Further refinement (2026-11-15, same day)

Same method: every step checked with `dev/run_build_checks.py`, `check_finishing_gates.py` (36/36, `--sixth` 41/41, `--determinism` 37/37) and the two padded development sets; 0 stale traps and 0 errors throughout; p95 ≤ 0.26 s.

| Step | Commit | Public | Reworded | Must-refuse | Chatty | Inline |
|---|---|---|---|---|---|---|
| Before | `b50a098` | 0.8822 | 0.8361 | 18/18 | 0.8434 | 0.6155 |
| General hours list schedules; isolated words dropped | `2752433` | **0.8868** | **0.854** | 18/18 | 0.8636 | 0.631 |
| Rate families always searched, relative cutoff | `1c70409` | 0.8868 | 0.854 | 18/18 | **0.8868** | **0.755** |
| Best of the three rarest words as required word | `3889133` | 0.8868 | **0.8675** | 18/18 | 0.8868 | **0.7783** |

- **General hours.** "What are your lobby hours?" with no branch named now gets the published schedules (newest first) and "Which branch do you need?", as the answer key's expected answer asks ("give a typical schedule and ask which branch"). Same mechanism as the comparison answer. "When can I visit…" reads as an hours question. dup-066 and its rewordings gain the source credit (0.85 → 1), dup-065-p2 0 → 1.
- **Isolated words.** A question word the site never uses in one passage with any other question word is dropped from matching (names kept). Words of one filler phrase still vouch for each other, so the effect is small; no public, reworded or must-refuse answer changed.
- **Rate families.** When a rate question names a family the site publishes rates for, its pages are always searched and only the relative cutoff (best − 0.15) applies to its rows, not the 0.35 floor. The family check is what makes such an answer correct; padding was lowering every row's score. Swept separately: pages only 0.631 inline, cutoff only 0.7085, both 0.755. No public, reworded or must-refuse answer text changed.
- **Required word.** Try each of the three rarest question words as the required word and keep the one whose best passage scores highest (a capitalised name is always tried; rate families keep their own check). Fixes dup-101-p2 (student loans); every changed answer is more on-topic.

**Rejected:** ordering the required word as names, then page-title words, then the rest (public 0.8868 → 0.8558: "Mullan Avenue" made "avenue" a name and broke the Mullan refusals).

## Second untouched test set (2026-11-15)

Written by another fresh Codex session, told not to open submission/, any of dev/ (so none of the earlier sets), PLAN.md, NOTES.md, README.md or results/, and not to run the system. 36 questions (4 per category; 19 public rewordings, 13 new, 4 refusals; styles 8 plain, 8 vocabulary, 8 conversational, 8 messy; 6 paraphrase groups; 4 historical as_of). Local only (`.git/info/exclude`): `dev/untouched2_eval.jsonl`, evidence in `dev/untouched2_evidence.md`.

Seal: `sha256sum dev/untouched2_eval.jsonl` → `0133d1cef681a323bbb86fc33f9ed18fa0a9eafc34fe3d79c221a7eb4f22e73e`, recorded before the run. Key check without running the system: every must_include value is in the snapshot the question's date selects (scorer's `contains()`) and on the expected source page; no must_not_include value overlaps the key. Run once at solution commit `3889133`; no fixes after it.

**Result of the one run** (`python3 harness/run_eval.py --submission submission --eval dev/untouched2_eval.jsonl --out results/untouched2`): final **0.6162** (first sealed set at the earlier commit: 0.3857), accuracy 0.6254, paraphrase consistency 0.83, repeat 1.0, p95 0.06 s, 0 stale traps, 0 errors. By category: entity 0.89, conflict 0.79, branch 0.75, should_refuse 0.75, stale_trap 0.75, current_value 0.54, temporal 0.50, tier 0.50, list 0.21. By the evidence file's style labels: vocabulary 0.86, plain 0.73, messy 0.52, conversational 0.36; public rewordings 0.72, new facts 0.46. 7 of 32 answerable questions refused; one must-refuse answered (drive-up window count at a branch → its address).

Diagnosis only (`python3 dev/trace_refusals.py --all --eval dev/untouched2_eval.jsonl`), no code changed:
- **The asked-sentence rule drops lowercase subjects in the context sentence** (2 items): "I am considering the 17-month certificate special, the regular one rather than jumbo. Could you tell me its annual yield?" is read as "annual yield" alone. Members put the subject in one sentence and ask about "its" or "that combination" in the next. Our padded set never did this, so it didn't show. A design flaw of `3260f07`, not a tuning gap.
- **Negation** ("non-jumbo", "rather than jumbo") is read as asking for jumbo (2 items).
- **Filler chosen as the required word** still ("flat", "hold"), 2 items.
- **Messy spelling** ("hometart", "12mo cd") and **wrong answer type** ("closing time" read as a date, "which page to trust" read as a link request), 4 items.
- **Lists of terms** ("every certificate term", "all terms on the rate table"), 2 items: no list answer over a table's term column.
- **Unanswerable detail about a real branch** ("How many drive-up windows does Galena have?") answered with the branch's address.
The set is now spent.

## Fixes 1 and 2 from the second sealed set's diagnosis (2026-11-15)

Fixed after reading the second sealed set's failures, so that set can no longer measure them. New development set `dev/context_eval.jsonl` (`python3 dev/make_context_eval.py`): 15 public facts asked with the subject in one sentence and "its"/"that" in the next (10), or with a product ruled out (5); public answer keys, hand-written wording.

| Commit | Public | Reworded | Must-refuse | Chatty | Inline | Two-sentence / negation |
|---|---|---|---|---|---|---|
| `3889133` | 0.8868 | 0.8675 | 18/18 | 0.8868 | 0.7783 | 0.3556 |
| `656f695` | 0.8868 | 0.8675 | 18/18 | **0.8984** | 0.7783 | **0.9933** |

- **Other sentences' words count, at weight 0.2.** Before, only their capitalised names were kept, so "I'm looking at your 17-month special certificate. What APY does it pay?" was read as "What APY does it pay?". They now count toward page coverage and passage score at CONTEXT_WEIGHT, are never the required word, and a rate family named only there is still found. Swept 0.5 / 0.3 / 0.2: chatty 0.8636 / 0.8965 / 0.8984, everything else equal; 0.5 let padding sentences pull answers off topic.
- **Ruled-out words.** "non-jumbo", "not the jumbo one", "rather than the Rewards Visa", "instead of the money market", "except…", "other than…": the word is removed from the question and rate rows that contain it are not answers. One word, two after "regular"/"standard"; a generic word ("not open") leaves the question unchanged. A first version took two words and turned "not open Saturday" into ruling out Saturday; fixed before commit.

Checks: no public, reworded or must-refuse item changed; practice 1.0; conflicts F1 0.759, 0/8 negatives; 0 stale traps; gates 36/36, `--sixth` 41/41, `--determinism` 37/37; p95 0.29 s. `dup-054-ctx1` (routing number with an employer sentence) lost the source credit (1 → 0.85).

## Third untouched test set (2026-11-15)

Written by a third fresh Codex session, told not to open submission/, any of dev/ (so none of the earlier sets), PLAN.md, NOTES.md, README.md or results/, and not to run the system. 36 questions (4 per category; 18 public rewordings, 14 new, 4 refusals; styles 8 plain, 8 vocabulary, 8 conversational, 8 messy; 6 paraphrase groups; 4 historical, 4 two-fact, 3 ruled-out-product questions). Local only (`.git/info/exclude`): `dev/untouched3_eval.jsonl`, `dev/untouched3_evidence.md`.

Seal: `sha256sum dev/untouched3_eval.jsonl` → `e39513d52cb97ba2ded1347f0384f7a3ef53e792c408bee10b3c2d9caec5ad88`, recorded before fixes 4–6 were written. Key check (printing only failures, so the questions stayed unread): all 36 keys in the snapshot the date selects and on the expected source; no must_not_include overlap. It will be run once, after fixes 4–6, with no fixes after it.

## Fixes 4–6 (2026-11-15)

Written after sealing the third untouched set (its questions unread). New development set `dev/shape_eval.jsonl` (`python3 dev/make_shape_eval.py`): 15 questions on public topics with keys read off the latest /rates table and public answer keys — typos and answer-type wording (8), lists of a family's terms (3), counts (4, three of them must refuse).

| Commit | Public | Reworded | Must-refuse | Chatty | Inline | Two-sentence | Shape (4–6) |
|---|---|---|---|---|---|---|---|
| `656f695` | 0.8868 | 0.8675 | 18/18 | 0.8984 | 0.7783 | 0.9933 | 0.2 |
| `42afaf8` | 0.8868 | 0.8675 | 18/18 | 0.8984 | 0.7783 | 0.9933 | **0.9333** |

- **Answer type.** "closing time" / "opening time" are hours questions, and "closing" is only a date question without "time", "hours" or "schedule". A link request needs "link", "URL", "website" or "which page lists/has/shows…"; "not sure which page to trust" is not one.
- **Typos** (`_respell`, applied to the message first). A lower-case word of 5+ letters the site never uses becomes two site words of 4+ letters run together ("hometart" → home tart), or the site word one slip away (dropped, added, changed or swapped letter) that the site uses in 10+ passages, never changing the first letter; a slip of a common word is corrected too ("curent" → current). Names and number words are left alone. Each guard came from a regression on our own sets: "three" → "tree" (dup-028-p2), "finder" → "binder"/"fender" (dup-080-p2), "weekdays" → "week day".
- **Stop words after stemming.** "whats" stemmed to "what" and became a required word; stop words are now also checked after stemming.
- **Lists of a family's terms.** "What terms can I choose for a personal loan?", "List every regular certificate term": a question naming a rate family with "terms" and a list word is a rate question, and lists every row of the winning table that passed the checks, not only the rows scoring as high as the winner. List words never count as the product's type ("every certificate") or as required row words.
- **Counts.** "How many X does … have?": a passage answers only if it states a number of X ("22 branches", "two windows"); "How many ATMs does the Galena branch have?" now refuses instead of giving the address. "branch offices" counts as the branch count.

Checks: no public, reworded, must-refuse, chatty or two-sentence item changed; practice 1.0; conflicts F1 0.759, 0/8 negatives; 0 stale traps; gates 36/36, `--sixth` 41/41, `--determinism` 37/37; p95 0.32 s. Left failing in the dev set: "hometart grant how much can i get" finds the right article but not its $15,000 sentence.

**Result of the third sealed set's one run** (`python3 harness/run_eval.py --submission submission --eval dev/untouched3_eval.jsonl --out results/untouched3`, solution commit `42afaf8`, hash checked): final **0.657** (set 2 at `3889133`: 0.6162; set 1 at `ad7587f`: 0.3857), accuracy 0.6873, paraphrase consistency 0.5, repeat 1.0, p95 0.09 s, 0 errors, **2 stale-trap hits**. By category: entity 1.00, stale_trap 1.00, tier 0.79, should_refuse 0.75, list 0.68, conflict 0.54, current_value 0.54, temporal 0.54, branch 0.25. By style: conversational 0.77 (set 2: 0.36), plain 0.73, messy 0.64, vocabulary 0.52; public rewordings 0.73, new facts 0.58. 4 of 32 answerable questions refused.

Diagnosis only (`python3 dev/trace_refusals.py --all --eval dev/untouched3_eval.jsonl`), no code changed:
- **Both stale-trap hits are the jumbo row next to the regular one.** "…leaving out the jumbo" is not a negation the rule knows; "the regular 17 month special cd" as of June lists both rows because "regular" doesn't rule out the jumbo variant.
- **Required word still a filler or answer word** (5): "street", "finish", "selection", "count", "charter" (the passage says "charter area" in a link the passage text lacks).
- **Coverage** (2): "What address should I put into my navigation app?", a historical jumbo question.
- **Two-part question with a count** ("fee per overdraft, and after how many days…") read as a count question.
- **Recognised article count with extra words** ("in the latest published count"), and "hometart … max grant" finds the article but not the $15,000 sentence.
- **One must-refuse answered** with an unrelated article.
The set is now spent.

## Tier fix (2026-11-15), from the third sealed set's two stale values

`2c9a3d5`. Added 4 items to `dev/context_eval.jsonl` (now 19), each with the jumbo special's APY (4.20%) as must_not_include: "leaving out the jumbo version", "without the jumbo minimum", "the regular 17-month certificate special", "standard 17 month special cd apy". Before: all four gave the jumbo row next to the regular one (stale-trap hit). After: all four correct.

- More ways of ruling out: "leaving out (the)", "without (the/a)", "skip(ping) (the)". A generic word after them leaves the question unchanged ("without a fee").
- "regular", "standard", "normal", "non-jumbo", when the message doesn't also say jumbo, rule out the jumbo rows: a jumbo row is another tier of the same product.

Checks: context 0.7842 → 0.9947; no public, reworded, must-refuse, chatty, inline or shape item changed; practice 1.0; conflicts F1 0.759, 0/8 negatives; 0 stale traps; gates 36/36, `--sixth` 41/41, `--determinism` 37/37.

## Python 3.11 verified (2026-11-15)

Installed `uv` 0.13.8 (`~/.local/bin`, shell profile untouched) and a Python 3.11.18 environment outside the repo (`~/.venvs/interface-311`). With the standard-library-only solution, on 3.11: public 0.8868, reworded 0.8675, must-refuse 1.0, practice 1.0, 0 errors, 0 stale traps; `check_finishing_gates.py` 36/36. One answer differed from 3.14 (dup-008): `urljoin` keeps an empty fragment ("…/savings-account#") on 3.14 and drops it on 3.11. `d8b7de8` strips it; after that every public, reworded and must-refuse answer is byte-identical on 3.11 and 3.14 (`results/pycmp/`). `--sixth` on 3.11: one run reported 40/41 while other checks ran; four further runs 41/41; the failing check was not printed and did not reproduce.

## Embedding experiment, tried and dropped (2026-11-15)

Tried `potion-base-8M` (model2vec, MIT, 30 MB, CPU only) in the Python 3.11 environment, run against public, reworded, must-refuse, chatty and inline (`sets2.sh` in the scratchpad, one run per setting):

| How it was used | Public | Reworded | Must-refuse | Chatty | Inline |
|---|---|---|---|---|---|
| Not used | 0.8868 | 0.8675 | 1.0 | 0.8984 | 0.7783 |
| Added to the match score, weight 0.1 | 0.8072 | 0.7861 | 1.0 | 0.7998 | 0.6987 |
| Added to the match score, weight 0.03 | 0.8072 | 0.7712 | 1.0 | 0.8171 | 0.6987 |
| Only to break near-ties in ranking | 0.8868 | 0.881 | 1.0 | 0.8973 | 0.776 |

Added to the score, loosely related blog text drew level with the rate rows. As a tie-breaker, only three scores moved: one reworded question gained (Hy-Vee branch members), and two padded routing-number questions lost their source credit. Ingest went from 47 s to 64 s.

**Decision: dropped.** The remaining misses happen before ranking (the right passage is never a candidate, or a rule rejects it), which re-ranking can't fix. One question isn't worth two dependencies and a 30 MB model, and the system stays standard library only. Code reverted, model deleted; public after the revert: 0.8868.

## GLOSSARY.md removed from the history (2026-11-15)

Q5 done. GLOSSARY.md is untracked and gitignored (kept locally), and the links to it in PLAN.md and dev/RESEARCH.md are gone. The history was rewritten with `git filter-branch --prune-empty --index-filter 'git rm --cached --ignore-unmatch GLOSSARY.md' -- main`: 69 commits became 68, because the commit that only added the glossary was dropped. Checks: `git log main -- GLOSSARY.md` is empty; no commit's tree contains GLOSSARY.md, the supplied snapshots, `.env` or the sealed sets; the final tree is identical to the pre-rewrite tip. A backup bundle of the old history is outside the repo. Force-pushed to origin/main.

## Repo cleanup before submission (2026-11-15)

Removed from the repo (all still in the git history, none confidential): `PRD.md` (one-page spec, superseded by NOTES.md), `dev/BUILD_REPORT.md` (a mid-build snapshot of scores, superseded by this file), `dev/REFUSAL_TRACE.md` (an early diagnosis; the code comment and the two mentions above now describe it instead of linking), and `Knowledge-Hackathon-Assignment.pdf` (the organizers' brief; kept locally and gitignored). README.md, which was the kit's brief, is now our own front page: results, how to run, and what's where. NOTES.md no longer says Python 3.11 is unverified, and it records the dropped embedding experiment. Checks: public 0.8868, 0 stale traps, 0 errors; `check_finishing_gates.py` 36/36; no remaining links to removed files (`git grep`).

## Fourth untouched test set (2026-11-15)

Written by a fresh Codex session, told not to open submission/, any of dev/, PLAN.md, NOTES.md, README.md, results/ or anything under /tmp, and not to run the system. 36 questions: 4 per category; 18 public rewordings, 14 new facts, 4 refusals; styles 9 plain, 9 vocabulary, 9 conversational, 9 messy; 6 paraphrase groups; at least 4 historical, 3 two-fact, 3 ruled-out-product, 3 tier and 3 branch questions. Local only (`.git/info/exclude`): `dev/untouched4_eval.jsonl`, `dev/untouched4_evidence.md`.

Seal: `sha256sum dev/untouched4_eval.jsonl` → `299fd9285877969324d6c68d01a54b111680a31576419ad2789cc5392fb50033`, recorded before any run. Key check without running the system (every must_include value is in the snapshot the question's date selects and on its expected source page; no must_not_include value overlaps the key): 36/36 OK. Plan: run it once on the current commit (aggregate only, no items read) and once after the next round, with no fixes between them that come from reading it.

## Answer-more round (2026-11-15)

Goal: refuse fewer answerable questions. The scorer gives 0 to a wrong refusal exactly as to a wrong answer, and only about 1 question in 9 should be refused, yet every sealed-set diagnosis found answerable questions refused. Sealed sets 1–3 are spent, so they are now development sets. Sealed set 4 is the judge (baseline on `560a225`, aggregate only: **0.5192**, 0 stale traps).

Decision number per step: the mean final score over 9 sets (public, reworded, chatty, inline, context, shape, sealed 1–3). A step is kept only if:
- the mean rises
- public doesn't fall and has 0 stale traps
- must-refuse stays at 15/18 or better
- conflicts and all gate scripts hold

Baseline `560a225`: public 0.8868, reworded 0.8675, must-refuse 18/18, chatty 0.8984, inline 0.7783, context 0.9947, shape 0.9333, sealed 1 0.5766, sealed 2 0.7313, sealed 3 0.7177; **mean 0.8205**.

**Tried first and dropped: required word as a penalty, not a veto.** A passage missing the required word scored ×0.3, ×0.5 or ×0.7 instead of being rejected. Not a single answer changed at any of the three settings. The trace (`dev/trace_refusals.py --all` on sealed 1–3) showed why: the rate refusals happen earlier, before the required word is checked.

**Step 1: find the product family of a rate question that doesn't name it.** Kept.
- **What was wrong.** "The 17-month fixed jumbo special" and "a 15-year fixed conventional home purchase" name no family word, so the rule "a rate question with no family refuses" fired.
- **The fix.** Such a question now takes the family whose rate rows use its distinctive words. A word counts only if at most 3 families' rows use it, weighted 1/(number of families using it). The best family needs a score of at least 1, and the runner-up must score below 0.6 of it. IRA is never inferred: it wraps certificates and savings, so only a question that says IRA asks for one.
- **Settings tried** (the setting and the mean it gave): spread ≤ 5 gave 0.8350; runner-up ratio 0.8 gave 0.8386; minimum 0.5 gave 0.8386. The chosen settings gave 0.8386.
- **"New" and "used" don't refuse.** They describe the vehicle, and the auto rows price it by model year. Before, "a 2024 used car" refused because "used" was read as an unknown product modifier.
- **Rejected:** accepting any modifier that the family's own pages use. It answered three must-refuse questions ("no penalty CD", "Bitcoin staking savings", "interest-only mortgage"), because "penalty", "staking" and "only" appear on those pages in other senses.

| | Public | Reworded | Must-refuse | Chatty | Inline | Context | Shape | S1 | S2 | S3 | Mean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Baseline | 0.8868 | 0.8675 | 18/18 | 0.8984 | 0.7783 | 0.9947 | 0.9333 | 0.5766 | 0.7313 | 0.7177 | 0.8205 |
| Step 1 | 0.8868 | 0.8675 | 18/18 | 0.8984 | 0.7783 | 0.9947 | 0.9333 | **0.6985** | **0.7933** | **0.7467** | **0.8442** |

Checks:
- 0 stale traps on every set.
- Gate scripts: 36/36, `--sixth` 41/41, `--determinism` 37/37.
- Conflicts: F1 0.759, resolution 1.0, 0/8 negatives.
- p95 under 0.6 s with ten suites running in parallel.

**Step 2: number words, and a family's own words only lower a row's score.** Kept.
- **More spelled-out terms.** "nine", "sixty", "twenty-four", "eighty-four"… are now read as numbers, and "60 monthly payments" counts as a 60-month term.
- **"Checking" the verb is not the product.** "I am checking an old offer" made a certificate question a Checking question.
- **A family word missing from a row lowers its score.** Before, a word of the question that the family's rows use anywhere (a "Tier" column header, "model") had to be in the row. Now each missing word halves the row's score (×0.5).
- **Words that name a row still must be in it.** Row-label words such as jumbo, Bright and Platinum must still be present, otherwise the row is another tier or product. The family's own name ("certificate") doesn't count as a row label.
- **Rejected: every missing word as a penalty.** It answered two must-refuse questions with the wrong row: "36-month jumbo certificate" got the regular 36-month row, and "Bright Savings on $5,000,000" got Share Savings. That is why row-label words stayed strict. The penalty was ×0.5 and ×0.8 in those two runs, and both gave the same answers.

| | Public | Reworded | Must-refuse | Chatty | Inline | Context | Shape | S1 | S2 | S3 | Mean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Step 2 | 0.8868 | 0.8675 | 18/18 | 0.8984 | 0.7783 | 0.9947 | 0.9333 | **0.7344** | **0.8613** | 0.7467 | **0.8557** |

Checks:
- 0 stale traps on every set.
- Gate scripts: 36/36, `--sixth` 41/41, `--determinism` 37/37.
- Conflicts: F1 0.759, resolution 1.0, 0/8 negatives.

**Step 3: address words describe the answer.** Kept.
- **What was wrong.** For an address question, "street", "ZIP", "address", "location" and "navigation" were scored as subject words. The site's address lines ("185 Peosta St., Peosta, IA, 52068") contain none of them, so the right line fell under the 0.35 score floor and the question was refused. These words are now dropped from an address question, as "link" and "page" already are for link questions.
- **Rejected: lower-case words the site writes as names.** "peosta" and "galena" are capitalised in at least 80% of their uses, so they could be kept as names. On its own this gave mean 0.8572 and pushed p95 to 2.4 s (a scan per word). Together with the address change it gave 0.8621, below the address change alone.

| | Public | Reworded | Must-refuse | Chatty | Inline | Context | Shape | S1 | S2 | S3 | Mean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Step 3 | 0.8868 | 0.8675 | 18/18 | 0.8984 | 0.7783 | 0.9947 | 0.9333 | **0.7794** | 0.8613 | **0.7637** | **0.8626** |

Checks:
- 0 stale traps on every set.
- Gate scripts: 36/36, `--sixth` 41/41, `--determinism` 37/37.
- Conflicts: F1 0.759, resolution 1.0, 0/8 negatives.

**Step 4: a link's address is not what a passage says.** Kept.
- **What was wrong.** Passage words included the addresses of markdown links, in the passage and in its heading context. So "[Continue](…/first-time-homebuyers-…-hometart-grants#) Cancel" and "[Keep reading](…hometart…)" matched a Home$tart question as well as the article did. They won, and the $15,000 sentence never showed.
- **The fix.** Link addresses are dropped before words are counted; the link labels stay. The Home$tart amount is now found (sealed 2 and 3, and shape-06). A Learning Lab hours question now reaches its article.
- **Rejected: also dropping article teasers** (a cut copy ending in "..." above a "Keep reading" link). It lost the Learning Lab item: mean 0.8747, against 0.8772 without it.

| | Public | Reworded | Must-refuse | Chatty | Inline | Context | Shape | S1 | S2 | S3 | Mean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Step 4 | 0.8868 | 0.8694 | 18/18 | 0.8984 | 0.7783 | 0.9947 | **1.0** | 0.7794 | **0.8974** | **0.7900** | **0.8772** |

Checks:
- 0 stale traps on every set.
- Gate scripts: 36/36, `--sixth` 41/41, `--determinism` 37/37.
- Conflicts: F1 0.759, resolution 1.0, 0/8 negatives.

**Step 5: a branch-count question may carry the member's own words.** Kept.
- **What was wrong.** The organisation-wide branch count (from dated articles) answered only when every other word of the question was generic. "How many branch offices should I list?", "…in the latest published count?" and "…these days?" all fell through to text search, which returned boilerplate without the number.
- **The fix.** Extra words are now allowed unless they set another scope: a capitalised name ("in Wisconsin"), a kind of place or service (state, city, county, drive-up, ATM, lobby, employees, members), or an award program's words.
- **Rejected: the same loosening for award questions.** It broke the gate "recognized for customer service may be another program" (36 → 35/36), so award questions still need every word to fit. That gave up dup-087-i1 (inline 0.8326 → 0.8093).

| | Public | Reworded | Must-refuse | Chatty | Inline | Context | Shape | S1 | S2 | S3 | Mean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Step 5 | 0.8868 | 0.8694 | 18/18 | 0.8984 | **0.8093** | 0.9947 | 1.0 | **0.8079** | 0.8974 | **0.8194** | **0.8870** |

Checks:
- 0 stale traps on every set.
- Gate scripts: 36/36, `--sixth` 41/41, `--determinism` 37/37.
- Conflicts: F1 0.759, resolution 1.0, 0/8 negatives.

**Step 6: a two-part question isn't a count or a date question.** Kept.
- **What was wrong.** "What is the fee per overdraft, and after how many days overdrawn…?" was read as a count question because of "how many". Only a passage stating a number of days could answer, and none did. "What's the maximum Home$tart help, and can it go toward the down payment or closing bill?" was read as a date question because of "closing".
- **The fix.** A question joining two asks (", and how/what/when/can…", or "both … and …") no longer takes the count or date shape.
- **Rejected: also dropping the rate and fee shapes for such questions.** It broke three rate questions, one of them a must-refuse rewording (reworded 0.8694 → 0.8393).

| | Public | Reworded | Must-refuse | Chatty | Inline | Context | Shape | S1 | S2 | S3 | Mean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Step 6 | 0.8868 | 0.8694 | 18/18 | 0.8984 | 0.8093 | 0.9947 | 1.0 | **0.8247** | 0.8974 | **0.8340** | **0.8905** |

Checks:
- 0 stale traps on every set.
- Gate scripts: 36/36, `--sixth` 41/41, `--determinism` 37/37.
- Conflicts: F1 0.759, resolution 1.0, 0/8 negatives.

**Sealed set 4, run once at `38f5ab1`** (`python3 harness/run_eval.py --submission submission --eval dev/untouched4_eval.jsonl`, hash checked):
- **Final 0.6398, against 0.5192 at `560a225` before this round.** Accuracy 0.6694, 1 stale trap, 0 errors, p95 0.2 s.
- **By category:** conflict 1.00, stale_trap 1.00, should_refuse 0.75, entity 0.75, tier 0.71, temporal 0.54, branch 0.50, current_value 0.50, list 0.07.

Diagnosis only, no code changed. The set is now spent. Most misses are gaps in kinds this round already worked on:
- **Vocabulary:** "promo CD" for the special, "satnav", "settlement costs", "biz".
- **A modifier the rows don't use:** "unsecured personal loan".
- **Two terms in one question:** "36 and 48 months", "half-year and one-year". Every qualifier number must be in the same row, so neither row passes.
- **"non jumbo" written with a space:** this produced the one stale trap (the jumbo 3.70% given).
- **Lists:** "all three business checking options", "both business Visa cards".
- **Filler questions:** a routing number and general lobby hours.
- **One must-refuse answered:** "rewards visa lowest fico score" got an unrelated article.
