"""Run the five agreed build checks with isolated local reports and item deltas.

Usage: python3 dev/run_build_checks.py STEP [--previous STEP]
Reports contain supplied data and stay in ignored results/build/.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step")
    ap.add_argument("--previous")
    args = ap.parse_args()
    out = ROOT / "results/build" / args.step
    out.mkdir(parents=True, exist_ok=True)
    base = [sys.executable, "harness/run_eval.py", "--submission", "submission"]
    commands = {
        name: base + ["--eval", path, "--out", str(out / name)]
        for name, path in [("public", "eval/public_eval.jsonl"),
                           ("reworded", "dev/paraphrase_eval.jsonl"),
                           ("refusal", "dev/refusal_eval.jsonl")]
    }
    commands["practice"] = base + ["--snapshots", "harness/selftest/snapshots", "--eval",
        "harness/selftest/eval.jsonl", "--conflicts-gold", "harness/selftest/conflicts_gold.json",
        "--out", str(out / "practice")]
    commands["conflicts"] = [sys.executable, "dev/check_conflicts.py"]
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")

    def run(entry):
        name, cmd = entry
        p = subprocess.run(cmd, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
        (out / (name + ".log")).write_text(p.stdout)
        if p.returncode:
            raise RuntimeError(f"{name}: exit {p.returncode}; see {out / (name + '.log')}")
        return name

    with ThreadPoolExecutor(max_workers=4) as pool:
        for name in pool.map(run, commands.items()):
            print("finished", name, flush=True)
    summary = {"commands": commands, "seed": "0", "sets": {}}
    for name in ("public", "reworded", "refusal", "practice"):
        report = json.loads((out / name / "report.json").read_text())
        rows = [json.loads(l) for l in (out / name / "per_question.jsonl").read_text().splitlines()]
        prev = {}
        if args.previous:
            path = out.parent / args.previous / name / "per_question.jsonl"
            prev = {r["id"]: r for r in map(json.loads, path.read_text().splitlines())}
        changed = {r["id"]: [prev[r["id"]]["score"], r["score"]]
                   for r in rows if r["id"] in prev and r["score"] != prev[r["id"]]["score"]}
        new_answers = [r["id"] for r in rows if r["id"] in prev
                       and r["category"] == "should_refuse"
                       and not prev[r["id"]]["answer"]["confident"] and r["answer"]["confident"]]
        summary["sets"][name] = dict(score=report["final_score"], qa=report["qa_score"],
            stale=report["stale_trap_hits"], errors=report["errors"],
            full=sum(r["score"] == 1 for r in rows), count=len(rows),
            changed=changed, newly_answered_refusals=new_answers)
    log = (out / "conflicts.log").read_text()
    summary["conflicts"] = json.loads(log[:log.index("}") + 1])
    summary["negative_failures"] = re.search(r"negatives failed: (\d+/\d+)", log).group(1)
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
