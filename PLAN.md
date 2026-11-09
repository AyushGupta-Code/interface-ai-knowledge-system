# Execution plan

Built from [PRD.md](PRD.md). Fill in each row as the work happens. "Done" needs evidence.

| Phase | What | Done | Evidence |
|---|---|---|---|
| Setup | Unzip the kit, `git init`, run the starter to get a baseline score | YES | Kit unzipped to repo root; `git init` done; CLAUDE.md, `.claude/settings.json` (deny list) and `.gitignore` (secrets) added. `python3 harness/run_eval.py --submission starter --eval eval/public_eval.jsonl` → `final_score 0.093`, 0 stale-trap hits, p95 0.45 s, 705 pages in the latest snapshot. |
| Research | Follow ~5 topics (a rate, a fee, branch hours, a promo, a tiered table) across all 5 snapshots; check where each of the 40 public answers lives; write down the rules for what counts as "current" | PENDING | |
| Decide | Settle the open question: LLM or no LLM, and how it runs without an API key | PENDING | |
| Build | `solution.py`: ingest with history, `answer` (current and "as of"), `conflicts` | PENDING | |
| Gates | Public eval ≥ 0.85; 0 stale-trap hits; p95 ≤ 2 s; our own reworded questions score close to the public set; runs from a fresh clone on Python 3.11 | PENDING | |
| Submit | `NOTES.md`, `requirements.txt`, push to the public GitHub repo (no snapshots, no API keys), email the repo link and commit to assignments@interface.ai | PENDING | |

**Deviations (declared when they happen, with why):**
- Setup: the Conflicts score (15%) can't be measured locally. The scorer only scores it with `--conflicts-gold`, and that file is in the organizers' private copy. Our local final score covers accuracy, consistency and speed only. We'll need our own check for `conflicts()` in Gates.
- Repo: public, not private. The PDF says private with read access, but interface.ai's email asks for a public repo without the supplied snapshots or API keys. `snapshots_zip/` is gitignored, so a fresh clone needs the kit's zips copied in before the scorer runs. NOTES.md must say so. This replaces the "runs from a fresh clone" gate.
