# PRD: Credit-union Q&A system that knows what's true now

## The outcome
A `solution.py` that answers members' questions from the five website snapshots with the current value and a source, and scores as close to 1.0 as possible on the hidden eval.

## Why
The assistant gave members wrong or out-of-date answers because the website contradicts itself across snapshots. A wrong rate is worse than "I don't know, please contact us."

## Scope
IN: current or "as of" answers, the right tier, a cited source, honest refusals, a list of contradictions.
OUT: no hard-coded answers, no live web calls, no edits to `harness/` or `eval/`, no UI, no website snapshots or API keys in the public repo.

## Definition of done
- [ ] `python harness/run_eval.py --submission <folder> --eval eval/public_eval.jsonl` runs from a fresh clone (plus the kit's snapshot zips) and scores ≥ 0.85, with 0 stale-trap hits.
- [ ] `NOTES.md` and `requirements.txt` are in the repo.

## Constraints
The `harness/contract.py` interface is fixed. Python 3.11. Answers must take ≤ 2 s at p95 (hard limit 60 s). Ingest must finish in < 30 min.

## Open questions
- Use an LLM? Will graders have an API key? (Assume no key; must run without one.)
