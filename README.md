# Credit-union Q&A that knows what's true now

My submission for the interface.ai knowledge hackathon. It answers credit-union members' questions from five dated snapshots of the credit union's website. Each answer gives the **current** value at the **right tier**, cites the page it came from, and refuses when the site doesn't say. It also lists where the site contradicts itself and which value wins.

It is plain Python 3.11 with the standard library only. There is no LLM, no API key, no network call and no third-party package.

## Results

| Set | Final score | Notes |
|---|---|---|
| Public eval (40 questions) | **0.9643** | 0 stale values, p95 0.13 s; the ceiling is 0.969 (one question has no required values) |
| Reworded public questions (written by me) | 0.8713 | |
| Questions the site doesn't answer | 18/18 refused | |
| Conflicts (local answer key) | F1 0.759 | right winner every time, 0/8 false conflicts |
| Five sealed sets written by a separate agent, each first run once | 0.386 → 0.616 → 0.657 → 0.519 → **0.711** | the honest estimate for unseen wording |

The first runs of the sealed sets are the most realistic measure. After each run, the set was used to find failure kinds, so their scores today (0.86–0.94) flatter the system. [NOTES.md](NOTES.md) explains how it decides, and where it still fails.

## Run it

**You need:** Python 3.11 or newer. Nothing to install: `submission/requirements.txt` is empty on purpose.

**1. Get the code.**

```bash
git clone https://github.com/AyushGupta-Code/interface-ai-knowledge-system.git
cd interface-ai-knowledge-system
```

**2. Add the snapshots.** They belong to the credit union, so they are not in this repo. Copy the kit's five zips into `snapshots_zip/`:

```
snapshots_zip/01_2026-05-12_baseline.zip
snapshots_zip/02_2026-05-19_recrawl.zip
snapshots_zip/03_2026-06-09_recrawl.zip
snapshots_zip/04_2026-08-27_rebaseline.zip
snapshots_zip/05_2026-09-28_latest.zip
```

The scorer unpacks them into `snapshots/` on its first run. You can also unzip them there yourself.

**3. Score it on the public eval.**

```bash
python3 harness/run_eval.py --submission submission --eval eval/public_eval.jsonl
```

To score another question set, pass its file to `--eval`, for example `--eval dev/paraphrase_eval.jsonl`. Loading the snapshots takes about 25 seconds. After that, each answer takes a fraction of a second.

**4. Ask your own questions.** From the repo root:

```python
import sys
from pathlib import Path
sys.path[:0] = ["harness", "submission"]
import run_eval, solution

kb = solution.build()
for snap in run_eval.load_snapshots(Path("snapshots")):
    kb.ingest(snap)

print(kb.answer("What is the APY on the 17-month certificate special?").text)        # today's value
print(kb.answer("What is the 12-month certificate APY?", "2026-05-20").text)       # as of a date
print(len(kb.conflicts()), "contradictions found")
```

**5. Optional: the checks run before every commit.**

```bash
python3 dev/check_conflicts.py                       # contradictions against the local answer key
python3 dev/check_finishing_gates.py                 # dates, fallback to older snapshots, caching (36 checks)
python3 dev/check_finishing_gates.py --sixth         # a sixth snapshot with one changed rate (41 checks)
python3 dev/check_finishing_gates.py --determinism   # same answers in separate processes (37 checks)
```

## What's where

| Path | What it is |
|---|---|
| [submission/solution.py](submission/solution.py) | The system: `build()` returns an object with `ingest`, `answer` and `conflicts` |
| [NOTES.md](NOTES.md) | How it works, the ten design decisions (D1–D10), and its limits |
| [PLAN.md](PLAN.md) | Step-by-step build log: every change, the command run, the real scores, and experiments that were dropped |
| [dev/](dev/) | My test sets (reworded, must-refuse, padded, context, shape), the scripts that make them, and the checks run before every commit |
| `harness/`, `eval/`, `starter/`, `snapshots/README.md` | The organizers' kit, unchanged |
| [CLAUDE.md](CLAUDE.md), `.claude/` | Rules for the AI coding assistant: never read secrets, never edit the organizers' files, never hard-code answers |
