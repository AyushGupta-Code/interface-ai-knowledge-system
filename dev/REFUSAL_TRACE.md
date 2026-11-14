# Refusal trace (step 2)

Where the evidence disappears for every question we refuse but should answer. Produced by
`python3 dev/trace_refusals.py` (reworded set) and `python3 dev/trace_refusals.py --eval eval/public_eval.jsonl`,
against commit `a4224b6` (answers identical to v2: public 0.6817, reworded 0.4737). No thresholds were changed
before this trace.

The tracer finds the evidence passages (the passages in the chosen snapshot holding the most Answer-key values,
using the scorer's `contains()`), then replays answer()'s stages on them and reports the furthest stage the
best evidence reached:

| Stage | Question asked |
|---|---|
| 1. Query | Were the words, qualifier numbers, answer shape and specific word read correctly? |
| 2. Page | Did the evidence page hold the right answer shape, and survive page coverage (≥ 0.5, and ≥ 0.75 × best)? |
| 3. Passage | Which check rejected it: shape, qualifier numbers, specific word, or score below the cutoff? |
| 4. Ranking | Did it pass every check and lose to another candidate? |

## Results: 12 wrong refusals (10 reworded, 2 public)

| Question | Where it stops | Root cause |
|---|---|---|
| dup-045 "Share Savings with a balance **between** $10,000 and $24,999" | 3. specific word | "between" chosen as the specific word |
| dup-046 "the **highest** Share Savings APY" | 3. specific word | "highest" |
| dup-045-p1 "Share Savings account **holding** $15,000" | 3. specific word | "holding" |
| dup-034-p2 "**list** your Visa cards and their interest rates" | 3. specific word | "list" |
| dup-074-p2 "When will the Hy-Vee location **shut** down?" | 3. specific word | "shut" (the site says "close") |
| dup-006-p2 "special rate as of **mid**-May 2026" | 3. specific word | "mid" left over from a date phrase |
| dup-064-p2 "What time do your lobbies open and close?" | 2. page cutoff | evidence pages at coverage 0.72 < 0.75 × best; the best page had no passing passage, so we refused instead of trying the next pages |
| dup-066-p2 "drive up window hours?" | 2. page cutoff | same: 0.62 < 0.75 × best |
| dup-008-p2 "Which page **lists** your share certificate rates?" | 2. page cutoff | 0.49 < 0.75 × best ("list" and "page" count as topic words) |
| dup-080-p2 "**link** to the Dupaco location finder" | 2. page coverage | no page reaches 0.5 ("link" is a topic word; "finder" is not site wording) |
| dup-060-p1 "How do I change my **address** or phone number?" | 1. query shape | read as "give me an address"; the question asks how to update details |
| dup-104-p2 "Do branch hours differ by location?" | 1. query / evidence | a yes/no comparison across branches; the tracer's evidence is weak here ("noon" also matches "afternoon") |

## What the trace says

1. **The specific-word rule (D9) causes half the wrong refusals (6 of 12, both public ones included).** Every time,
   the word chosen is a filler or wording word (between, highest, holding, list, shut, mid), never the product.
   Rarity alone can't separate filler from subject words; this confirms the earlier page-count finding
   (top 135 pages, share 159, student 202).
2. **Page selection refuses too early (4 of 12).** When the best-covered page yields no passing passage, we refuse
   instead of moving on to the next pages. Words that describe the *kind* of answer ("link", "page", "list")
   also count as topic words and dilute coverage.
3. **Answer shape is read from words, not intent (2 of 12).** "change my address" is not an address question.
4. **No case stopped at ranking (stage 4).** Evidence that survived the checks always won.

None of the 12 needs a broad threshold change. The fixes are targeted at the stage that dropped the evidence.

## After the fixes (step 3)

Applied: wording words can't be the specific word; synonyms (shut down → close, holding → balance,
drive-up window → drive-up); "mid-May" style date prefixes dropped; answer-kind words (link, page, list) removed
from topic words; page fallback to every page covering half the question before refusing; "how do I change…"
read as a procedure question.

Re-trace: 12 → 2 wrong refusals. Left: dup-080-p2 ("location finder": the site says "Find a branch", and adding
that synonym would be fitting one question) and dup-104-p2 (a yes/no comparison across branches, which needs
a different answer type). Public 0.7282, reworded 0.5619, should_refuse still 3/3 on public.
