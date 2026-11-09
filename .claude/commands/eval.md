---
description: Run the scorer on a submission folder (default: submission)
argument-hint: "[folder]"
---

Run the hackathon scorer from the repo root:

```
python3 harness/run_eval.py --submission ${ARGUMENTS:-submission} --eval eval/public_eval.jsonl
```

If no folder was given, use `submission`. If that folder doesn't exist yet, say so and suggest `/eval starter`.

Then report:
1. `final_score` and the pillar scores, compared with the last score recorded in PLAN.md.
2. Any stale-trap hits or errors.
3. The weakest categories, and the questions missed there (read `results/per_question.jsonl`, which the scorer writes).

Don't edit any files. Recording the result in PLAN.md is a separate step.
