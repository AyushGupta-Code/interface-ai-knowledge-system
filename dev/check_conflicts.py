"""Our own benchmark for conflicts() (the organizers' conflict gold is private).

Positives: dev/conflicts_gold.json, in the scorer's gold format plus our evidence fields. Scored with the
scorer's own score_conflicts(), so precision, recall, F1 and resolution mean what they mean at grading.
Negatives: dev/conflicts_negative.json. A negative fails when one submitted conflict lists all its values
as separate competing entries and its topic names one of the keywords (e.g. two balance tiers reported
as a contradiction).

Usage: python3 dev/check_conflicts.py [--snapshots snapshots] [--show]
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))
import run_eval  # noqa: E402
from scoring import _norm, contains, score_conflicts  # noqa: E402


def matches(conflict, gold) -> bool:
    """The scorer's matching rule, for reporting which gold entry each conflict hit."""
    vals = " | ".join(conflict.values or [])
    vhits = sum(contains(vals, v) for v in gold["values"])
    khit = any(_norm(k) in _norm(conflict.topic or "") for k in gold.get("topic_keywords", []))
    return vhits >= 2 or (vhits >= 1 and khit)


def trips(conflict, neg) -> bool:
    if not any(_norm(k) in _norm(conflict.topic or "") for k in neg["topic_keywords"]):
        return False
    homes = [[i for i, e in enumerate(conflict.values or []) if contains(e, v)] for v in neg["values"]]
    if not all(homes):
        return False
    # competing = each value has an entry of its own, not all inside one entry (e.g. "4.10% APY / 4.06% dividend")
    return len({i for h in homes for i in h}) > 1 and not any(set.intersection(*map(set, homes)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshots", type=Path, default=ROOT / "snapshots")
    ap.add_argument("--submission", type=Path, default=ROOT / "submission")
    ap.add_argument("--show", action="store_true", help="print every submitted conflict")
    args = ap.parse_args()

    gold = json.loads((ROOT / "dev/conflicts_gold.json").read_text())
    negs = json.loads((ROOT / "dev/conflicts_negative.json").read_text())
    ks = run_eval.load_submission(args.submission)
    for s in run_eval.load_snapshots(args.snapshots):
        ks.ingest(s)
    t = time.time()
    subs = ks.conflicts()
    secs = time.time() - t

    report = score_conflicts(gold, subs)
    print(json.dumps(report, indent=2))
    print(f"conflicts() took {secs:.2f} s, {len(subs)} conflicts")
    print("\ngold entries (assigned like the scorer: gold in order, first unused matching conflict):")
    used = set()
    for g in gold:
        i = next((i for i, c in enumerate(subs) if i not in used and matches(c, g)), None)
        used.add(i)
        hit = None if i is None else subs[i]
        res = "" if not hit else (" resolution OK" if contains(hit.resolution or "", g["correct_value"]) else
                                  f" resolution WRONG ({hit.resolution})")
        print(f"  {'HIT ' if hit else 'MISS'} {g['id']:28} {('-> ' + hit.topic) if hit else ''}{res}")
    print("\nnegative examples:")
    bad = 0
    for n in negs:
        tripped = [c.topic for c in subs if trips(c, n)]
        bad += bool(tripped)
        print(f"  {'FAIL' if tripped else 'ok  '} {n['id']:28} {tripped[:2] if tripped else ''}")
    if args.show:
        print("\nsubmitted:")
        for c in subs:
            print(f"  {c.topic} | {c.values} | {c.resolution}")
    print(f"\nnegatives failed: {bad}/{len(negs)}")


if __name__ == "__main__":
    main()
