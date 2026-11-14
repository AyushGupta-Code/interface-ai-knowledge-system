"""Behavioral finishing gates; synthetic cases are development fixtures, not a holdout set.

Run ``python3 dev/check_finishing_gates.py`` for synthetic temporal/fallback/cache cases.
Add ``--sixth`` for a full local copy plus one changed October rate, or ``--determinism``
for independent processes with three hash seeds. All snapshot copies stay in /tmp and
are deleted on exit. No supplied website text is written into tracked files.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))
import run_eval  # noqa: E402
from contract import Page, Snapshot  # noqa: E402


def page(path: str, title: str, text: str) -> Page:
    return Page("https://fixture-credit-union.test" + path, title, text, "")


def snapshot(date: str, pages: list[Page]) -> Snapshot:
    return Snapshot("fixture_" + date, date, pages)


def build(submission: Path, snapshots: list[Snapshot]):
    system = run_eval.load_submission(submission)
    for item in snapshots:
        system.ingest(item)
    return system


def source_date(answer, snapshot_id: str) -> bool:
    return any(s.snapshot_id == snapshot_id for s in answer.sources)


def synthetic_checks(submission: Path) -> list[tuple[str, bool, str]]:
    checks = []
    first, latest = "2026-01-05", "2026-03-01"
    fee_question = "How much is a lost debit card replacement?"
    fee = page("/fees", "Fees", "# Fees\n\nLost debit card replacement fee: $2.50")
    unrelated = page("/contact", "Contact", "# Contact\n\nPlease contact the credit union for assistance.")
    old = snapshot(first, [fee])
    missing = build(submission, [old, snapshot(latest, [unrelated])])
    answer = missing.answer(fee_question)
    history_label = (first in answer.text and
                     bool(re.search(r"histor|last (?:shown|seen|observed)|can't confirm|cannot confirm", answer.text, re.I)))
    checks.append(("missing fee is dated history", "$2.50" in answer.text and history_label
                   and source_date(answer, old.snapshot_id), "value, observation date, history label, older source"))
    checks.append(("no fallback before first snapshot", not missing.answer(fee_question, "2025-12-31").confident,
                   "date before all observations"))
    changed = snapshot(latest, [page("/fees", "Fees", "# Fees\n\nLost debit card replacement fee: $3.75")])
    system = build(submission, [old, changed])
    for name, date, expected, excluded in [
        ("exact first snapshot", first, "$2.50", "$3.75"),
        ("between snapshots", "2026-02-10", "$2.50", "$3.75"),
        ("exact latest snapshot", latest, "$3.75", "$2.50"),
        ("after latest snapshot", "2026-12-01", "$3.75", "$2.50"),
    ]:
        answer = system.answer(fee_question, date)
        checks.append((name, expected in answer.text and excluded not in answer.text, "selected snapshot fee"))
    withdrawn = snapshot(latest, [page("/fees", "Fees", "# Fees\n\nLost debit card replacement fee has been withdrawn and is no longer published.")])
    answer = build(submission, [old, withdrawn]).answer(fee_question)
    checks.append(("withdrawal prevents fallback", "$2.50" not in answer.text,
                   "an explicit withdrawal must not resurrect an old fee"))
    withdrawn_rate = page("/rates/certificates", "Certificate Rates", "# Certificates\n\n6-month certificate APY: 2.95%")
    withdrawal_notice = page("/announcements/status", "Product Status", "# Product Status\n\nThe 6-month certificate is no longer available.")
    cross_url = build(submission, [snapshot(first, [withdrawn_rate]), snapshot(latest, [withdrawal_notice])])
    answer = cross_url.answer("What is the 6-month certificate APY?")
    checks.append(("different-URL withdrawal prevents fallback", "2.95%" not in answer.text,
                   "a selected-snapshot notice blocks history even without rate answer shape"))
    promo = page("/promo", "Certificate Promotion", "# Certificate Promotion\n\n6-month certificate APY: 3.50%\n\nOffer expired 2026-02-01.")
    promotion_system = build(submission, [snapshot(first, [promo]), snapshot(latest, [unrelated])])
    answer = promotion_system.answer("What is the 6-month certificate APY?")
    checks.append(("expired promotion prevents fallback", "3.50%" not in answer.text,
                   "expiration precedes selected snapshot date"))
    before_expiry = promotion_system.answer("What is the 6-month certificate APY?", "2026-01-15")
    checks.append(("promotion evidence exists before expiry", "3.50%" in before_expiry.text,
                   "paired positive prevents a vacuous expired-promotion pass"))
    rates_first = page("/rates", "Certificate Rates", "# Certificates\n\n6-month certificate APY: 2.95%")
    rates_latest = page("/rates", "Certificate Rates", "# Certificates\n\n6-month certificate APY: 3.50%")
    one = snapshot(first, [rates_first])
    two = snapshot(latest, [rates_latest])
    system = build(submission, [one])
    before = system.answer("What is the 6-month certificate APY?")
    system.conflicts()  # Populate both answer and conflict caches before another ingest.
    system.ingest(two)
    after = system.answer("What is the 6-month certificate APY?")
    history = system.answer("What is the 6-month certificate APY?", first)
    conflicts = system.conflicts()
    checks.append(("ingest refreshes answer cache", "2.95%" in before.text and "3.50%" in after.text
                   and "2.95%" not in after.text, "current moves after ingestion"))
    checks.append(("ingest preserves as-of history", "2.95%" in history.text and "3.50%" not in history.text,
                   "earlier snapshot remains available"))
    checks.append(("ingest refreshes conflicts and resolution", any("2.95" in " ".join(c.values)
                   and "3.5" in " ".join(c.values) and "3.5" in (c.resolution or "") for c in conflicts),
                   "changed fact appears and resolves to newest observation"))
    # Current evidence for another term must not trigger historical fallback to this term.
    other_term = page("/rates", "Certificate Rates", "# Certificates\n\n12-month certificate APY: 3.10%")
    answer = build(submission, [one, snapshot(latest, [other_term])]).answer("What is the 6-month certificate APY?")
    checks.append(("term mismatch does not trigger fallback", "2.95%" not in answer.text,
                   "current family evidence exists, but requested term does not match"))
    absent = build(submission, [one, snapshot("2026-02-01", [rates_latest]), snapshot(latest, [unrelated])])
    historical = [c for c in absent.conflicts()
                  if "2.95" in " ".join(c.values) and "3.5" in " ".join(c.values)]
    checks.append(("missing current fact has no current conflict resolution", bool(historical)
                   and all(not c.resolution for c in historical),
                   "retain observed change, but absent latest fact cannot resolve as current"))
    # Parser invariants use synthetic values and exercise units without answer-key coupling.
    helpers = type(system).answer.__globals__
    question_numbers = helpers["question_numbers"]
    numbers_ok = helpers["numbers_ok"]
    checks.append(("year/month terms use equivalent units",
                   numbers_ok(question_numbers("What is the three-year certificate APY?"), "36-month certificate APY: 3.10%")
                   and numbers_ok(question_numbers("What is the 36-month certificate APY?"), "3-year certificate APY: 3.10%"),
                   "3 years and 36 months identify the same term"))
    checks.append(("percentage cannot satisfy a term qualifier",
                   not numbers_ok(question_numbers("What is the six-month certificate APY?"), "12-month certificate APY: 6%"),
                   "a 6% rate is not evidence of a six-month term"))
    checks.append(("article classification precedes rates fallback",
                   helpers["page_kind"]("https://fixture-credit-union.test/newsroom/rates") == "article",
                   "a rate path segment cannot upgrade a known article"))
    checks.append(("multi-value labeled rate is rejected",
                   not helpers["labeled_rate"]("6-month certificate APY: 3.50% / 3.10%"),
                   "ambiguous multi-value prose must not become one structured fact"))
    return checks


def sixth_snapshot_checks(submission: Path, source: Path) -> list[tuple[str, bool, str]]:
    """Copy all snapshots and add a full sixth snapshot with one APY cell changed."""
    with tempfile.TemporaryDirectory(prefix="interface-finishing-", dir="/tmp") as temp:
        copied = Path(temp) / "snapshots"
        shutil.copytree(source, copied)
        dirs = sorted(p for p in copied.iterdir() if (p / "manifest.json").exists())
        october = copied / "06_2026-10-15_synthetic"
        shutil.copytree(dirs[-1], october)
        manifest_path = october / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        previous_date = manifest["taken_on"]
        manifest.update(snapshot_id=october.name, taken_on="2026-10-15")
        target = next(p for p in manifest["pages"] if p["url"].rstrip("/") == "https://www.dupaco.com/rates")
        target_path = october / target["file"]
        text, count = re.subn(r"(\| 12 Month \|[^\n]*?\|\s*)3\.40%(\d*)(\s*\|)", r"\g<1>4.44%\2\3", target_path.read_text())
        if count != 1:
            raise RuntimeError("Expected exactly one 12-month APY cell in the latest rate hub")
        target_path.write_text(text)
        for item in manifest["pages"]:
            item["fetched_at"] = "2026-10-15T00:00:00Z"
        manifest_path.write_text(json.dumps(manifest))
        snapshots = run_eval.load_snapshots(copied)
        system = build(submission, snapshots)
        question = "What is the 12-month certificate APY?"
        answer = system.answer(question)
        past = system.answer(question, previous_date)
        return [
            ("sixth snapshot is full", len(snapshots) == len(dirs) + 1 and len(snapshots[-1].pages) == len(snapshots[-2].pages),
             "all prior snapshots copied; October has all latest pages"),
            ("sixth snapshot current rate", "4.44%" in answer.text and source_date(answer, october.name),
             "synthetic APY and October source"),
            ("sixth snapshot preserves prior as-of", "3.40%" in past.text and "4.44%" not in past.text,
             "September APY is unchanged"),
            ("sixth snapshot conflict resolution", any("4.44%" in (c.resolution or "") for c in system.conflicts()),
             "synthetic new value is the conflict resolution"),
        ]


def determinism_digest(submission: Path, snapshots: Path) -> str:
    system = build(submission, run_eval.load_snapshots(snapshots))
    answers = []
    for filename in ["eval/public_eval.jsonl", "dev/paraphrase_eval.jsonl", "dev/refusal_eval.jsonl"]:
        for line in (ROOT / filename).read_text().splitlines():
            if line.strip():
                item = json.loads(line)
                answers.append(asdict(system.answer(item["question"], item.get("as_of"))))
    payload = {"answers": answers, "conflicts": [asdict(c) for c in system.conflicts()]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def determinism_checks(submission: Path, snapshots: Path, interpreter: str) -> list[tuple[str, bool, str]]:
    digests = []
    for seed in ["0", "1", "42"]:
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([interpreter, str(Path(__file__).resolve()), "--determinism-worker",
                                 "--submission", str(submission), "--snapshots", str(snapshots)],
                                env=env, capture_output=True, text=True, check=True)
        digests.append(result.stdout.strip())
    return [("independent-process determinism", len(set(digests)) == 1,
             "; ".join(f"seed {seed}: {digest}" for seed, digest in zip([0, 1, 42], digests)))]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", type=Path, default=ROOT / "submission")
    parser.add_argument("--snapshots", type=Path, default=ROOT / "snapshots")
    parser.add_argument("--sixth", action="store_true")
    parser.add_argument("--determinism", action="store_true")
    parser.add_argument("--python", default=sys.executable, help="interpreter for independent determinism runs")
    parser.add_argument("--determinism-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.determinism_worker:
        print(determinism_digest(args.submission, args.snapshots))
        return
    checks = synthetic_checks(args.submission)
    if args.sixth:
        checks.extend(sixth_snapshot_checks(args.submission, args.snapshots))
    if args.determinism:
        checks.extend(determinism_checks(args.submission, args.snapshots, args.python))
    for name, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL'} {name}: {detail}")
    failed = sum(not passed for _, passed, _ in checks)
    print(json.dumps({"checks": len(checks), "passed": len(checks) - failed, "failed": failed}))
    raise SystemExit(bool(failed))


if __name__ == "__main__":
    main()
