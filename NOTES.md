# Notes

The system answers members' questions from five dated snapshots of the credit union's website. Each answer gives the current value, the right tier and a source, or says "I don't know" when the site doesn't say.

**No API keys, no packages, no network.** It is plain Python 3.11 with the standard library only. There is no language model. `requirements.txt` is empty on purpose.

**To run it:** the snapshots aren't in this repo (the data must not be redistributed). Copy the kit's five zips into `snapshots_zip/`, then run:

```bash
python3 harness/run_eval.py --submission submission --eval eval/public_eval.jsonl
```

Loading the snapshots takes about 45 seconds. After that, each answer takes well under a second.

## How it decides what's true now

1. **Pick the snapshot by date.** With no date, use the newest snapshot. With "as of" a date, use the newest snapshot on or before that date.
2. **Trust pages in a fixed order.** The rates page wins over a product page. A product page wins over a promotion, which wins over a calculator, then a blog post or news article, then a file. Among articles, the newer one wins.
3. **Keep tiers apart.** A 12-month and a 60-month rate, a regular and a jumbo certificate, or a personal and a business account are different facts, not a contradiction.
4. **Keep measures apart.** APR, APY and dividend rate are different numbers. The answer uses the one that was asked for.
5. **Refuse rather than guess.** The question's product and its important words must be in the passage that answers it. If they aren't, the system says it can't find the answer, and it gives no number.
6. **Contradictions are the same fact with different values.** They are either a **change** between snapshots or a **disagreement** between two pages in the same snapshot. Each one names the winning value and the reason.

## How we got here, in phases

Every change was checked with the scorer before it was kept. Every score below is the organizers' public set unless it says otherwise. [PLAN.md](PLAN.md) has the full log: each step, the command and the real output.

**Phase 0. Starter: 0.093.** The organizers' starter kept only the latest copy of each page and returned the paragraph sharing the most words with the question. It ignored dates and found no contradictions.

**Phase 1. Read the site before writing code.** For each of the 40 public questions, a script found the page holding the right answer and the page holding each wrong one. The wrong values came from five places:
- another product on the same rate page
- an old page that is still live
- a calculator that was never updated
- an old news article
- an expired promotion

That gave us the page-trust order above. We also decided against using an LLM (decision D1 below).

**Phase 2. First version: 0.417.** It indexed every sentence, list and table row, with its page and date. Three failures, all fixed:
- headings won over the text under them
- the refusal message contained a phone number, which the scorer counts as giving a number
- the year in "as of May 2026" was read as a product detail

**Phase 3. Two-step search: 0.682.** First pick the pages that are about the question and hold an answer of the right type (a rate, a fee, hours, an address). Then pick the best passage on those pages. But our own reworded versions of the public questions scored only 0.47. The system was too fragile to wording.

**Phase 4. Trace each wrong refusal: 0.774.**
- **Tracing.** We followed every wrong "I don't know" to the step where the right passage was lost. Most of them had treated a filler word ("between", "highest") as the word the answer must contain.
- **Rate questions.** These are now checked against the product's own rate rows. An unknown product ("Unicorn savings") is refused.
- **Contradictions.** We rebuilt the list from facts instead of raw table rows. On our own answer key, its score (F1) went from 0.04 to 0.76.
- **Tried and dropped:** stricter subject checks lowered the public score to 0.686.

**Phase 5. The organizers' practice test, history and links: 0.851.**
- Rates written as "label: value" lines are read as well as tables.
- If a snapshot doesn't have a fact at all, an older value can be given, clearly labelled as old.
- "Where can I find…" questions get the link itself.
- Article counts (branches, awards) answer questions.
- **The bug a fake sixth snapshot caught.** We made a fake October snapshot with one changed rate. A list answer showed the new rate next to the old one copied on a product page. Lists now keep one value per fact.

**Phase 6. A second opinion from Codex: 0.882, and 18/18 on questions the site can't answer.** We added three narrow rules:
- An award question needs the named organisation giving the award.
- "How do I change my address?" with no steps on the site gets the general phone number.
- "Do all branches keep the same hours?" lists each published schedule.

**Phase 7. The first sealed test: 0.386.** Codex wrote 36 new questions without seeing our code, and we ran them once. 20 of the 32 questions the site can answer were refused. Members write conversationally ("I'm stopping at the Peosta branch…"), and the filler words were taken as the subject. We fixed the mechanism, measuring it on padded copies of the public questions:
- Only the sentence that asks the question is read; names from the other sentences are kept.
- The word the answer must contain is chosen from the three rarest words.
- A named rate family is always searched.

Padded questions went from 0.32 to 0.89. Public rose to 0.887.

**Phase 8. The second sealed test: 0.616.** New failures appeared:
- the subject was in one sentence and "its" in the next
- "non-jumbo" was read as asking for jumbo
- typos ("hometart")
- "closing time" was read as a date
- list questions ("every certificate term")
- an unanswerable count ("how many drive-up windows") was answered with an address

We fixed all six as general rules, not answers to those questions. The other sentences now count a little, and ruled-out words exclude rows.

**Phase 9. The third sealed test: 0.657.** Conversational questions went from 0.36 to 0.77. Two answers gave the jumbo rate next to the regular one ("leaving out the jumbo", "the regular special"). Now "regular", "standard" and more ways of ruling something out exclude the jumbo rows. No fresh test has measured this fix yet.

**Phase 10. Embeddings tried, then dropped.** We tried a small local embedding model (potion-base-8M). Added to the match score, it dropped the public score to 0.807. Used only to break ties, it fixed one reworded question. One question wasn't worth two packages and a 30 MB model. We also confirmed the system gives the same answers on Python 3.11 as on 3.14.

## Results at the submitted commit

| Test | Score |
|---|---|
| Public set (40 questions) | **0.887**, 0 stale values, 95% of answers under 0.3 s |
| Our rewordings of the public questions | 0.868 |
| Questions the site can't answer (ours) | 18/18 refused |
| Contradictions (our own answer key) | F1 0.76, right winner every time, 0 of 8 false contradictions |
| Sealed sets written by a separate agent | 0.386, then 0.616, then 0.657 |

The sealed sets are the honest estimate for new wording. Our own sets were used while building, so they flatter the system.

## Decisions

The code comments refer to these labels.

- **D1. No language model.** Rules can be explained line by line and need no key. The cost is weaker handling of unfamiliar wording.
- **D2. Values come only from the snapshots.** Nothing is hard-coded from the eval questions.
- **D3. Keep every snapshot.** Old snapshots answer "as of" questions and show changes. They never decide today's value.
- **D4. Choose the snapshot by date.** Use an older snapshot only when the chosen one has no evidence at all, and label it as old.
- **D5. One fact model.** Tables and "label: value" lines become the same kind of fact.
- **D6. Trust pages in order.** Rates page, product page, promotion, calculator, article, then file.
- **D7. Tiers are different facts.** Terms, balances, model years, personal and business are kept apart.
- **D8. Measures are different facts.** APR, APY, dividend and interest rate are kept apart.
- **D9. Refuse rather than substitute.** An unknown product or feature is refused instead of being matched to a nearby one.
- **D10. Changes and disagreements are reported separately.** Dates show when a value was seen, not when it took effect.

## What it still gets wrong

- **Filler words inside the question.** "What street should I type into…" can make "street" the word the answer must contain.
- **Branch-specific questions** (0.25 on the third sealed set).
- **Membership eligibility.** The site lists its service-area states separately from its eligibility rules, and the system doesn't join the two.
- **One public question with no required values** scores zero under the default scorer, whatever the answer.
