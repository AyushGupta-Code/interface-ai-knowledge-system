# Credit-union Q&A that knows what's true now

My submission for the interface.ai knowledge hackathon. It answers credit-union members' questions from five dated snapshots of the credit union's website. Each answer gives the **current** value at the **right tier**, cites the page it came from, and refuses when the site doesn't say. It also lists where the site contradicts itself and which value wins.

It is plain Python 3.11 with the standard library only. There is no LLM, no API key, no network call and no third-party package.

## Results

| Set | Final score | Notes |
|---|---|---|
| Public eval (40 questions) | **0.8868** | 0 stale values, p95 under 0.3 s |
| Reworded public questions (written by me) | 0.8675 | gap to public 0.019 |
| Questions the site doesn't answer | 18/18 refused | |
| Conflicts (local answer key) | F1 0.759 | right winner every time, 0/8 false conflicts |
| Three sealed sets written by a separate agent, each run once | 0.386 → 0.616 → 0.657 | the honest estimate for unseen wording |

The sealed sets are the most realistic measure. Conversational and messy wording is still the main weakness. [NOTES.md](NOTES.md) explains why.

## Run it

The website snapshots belong to the credit union and are not in this repo. Put the kit's five snapshot zips in `snapshots_zip/`; the scorer unpacks them on its first run. Then, from the repo root:

```bash
python3 harness/run_eval.py --submission submission --eval eval/public_eval.jsonl
```

Ingest takes about 45 seconds. After that, each answer takes a fraction of a second.

## What's where

| Path | What it is |
|---|---|
| [submission/solution.py](submission/solution.py) | The system: `build()` returns an object with `ingest`, `answer` and `conflicts` |
| [NOTES.md](NOTES.md) | How it works, the ten design decisions (D1–D10), and its limits |
| [PLAN.md](PLAN.md) | Step-by-step build log: every change, the command run, the real scores, and experiments that were dropped |
| [dev/](dev/) | My test sets (reworded, must-refuse, padded, context, shape), the scripts that make them, and the checks run before every commit |
| `harness/`, `eval/`, `starter/`, `snapshots/README.md` | The organizers' kit, unchanged |
| [CLAUDE.md](CLAUDE.md), `.claude/` | Rules for the AI coding assistant: never read secrets, never edit the organizers' files, never hard-code answers |
