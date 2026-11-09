# Credit-union Q&A (interface.ai knowledge hackathon)

<!-- Keep it short: only what Claude can't infer from the code. -->

## What this is
A Q&A system that answers Dupaco credit-union members' questions from five website snapshots (May–Sep 2026), using the current value, the right tier and a source, and refusing honestly when the site doesn't say. Spec: [PRD.md](PRD.md). Progress: [PLAN.md](PLAN.md). The assignment brief is `Knowledge-Hackathon-Assignment.pdf`.

## Conventions
- Python 3.11 at grading. Our solution goes in `submission/solution.py` (any folder except `starter/`).
- Test with `/eval` (or `/eval starter`). Don't type the raw command. It runs `python3 harness/run_eval.py --submission submission --eval eval/public_eval.jsonl`.
- `harness/` and `eval/` are the organizers' files. Never edit them.
- Never hard-code answers to the public eval questions. The hidden set rewords them.
- Update PLAN.md as work happens, with evidence (the command and its real output). Declare deviations when they happen.

## Security
- Secrets live in `.env` / `.secrets/` (gitignored). Never commit them, never paste them into an external model.
- The repo is public. The supplied website snapshots (`snapshots_zip/`, `snapshots/0*/`) are a real credit union's site and must never be committed. Both are gitignored.
- Commit after every change that passes `/eval`, using `type(scope): what` messages (e.g. `feat(answer): ...`). Push only when asked.
