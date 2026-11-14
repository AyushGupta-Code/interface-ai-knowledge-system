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
    product_first = page("/personal/certificate", "Certificate Rates", "# Certificates\n\n6-month certificate APY: 3.10%")
    hub_corrected = page("/rates", "Certificate Rates", "# Certificates\n\n6-month certificate APY: 3.10%")
    provenance_system = build(submission, [snapshot(first, [rates_first, product_first]),
                                            snapshot(latest, [hub_corrected, product_first])])
    provenance_conflicts = provenance_system.conflicts()
    disagreements = [c for c in provenance_conflicts if "disagreement" in c.topic.lower()]
    expected_pair = {(rates_first.url, "fixture_" + first), (product_first.url, "fixture_" + first)}
    checks.append(("disagreement preserves contemporaneous source pair", bool(disagreements)
                   and all(expected_pair <= {(s.url, s.snapshot_id) for s in c.sources}
                           and first in (c.reason or "") and rates_first.url in (c.reason or "")
                           and product_first.url in (c.reason or "") for c in disagreements),
                   "both differing pages cite January, although March pages agree"))
    checks.append(("disagreement does not blame the product page", bool(disagreements)
                   and all(not re.search(r"\bstale\b|never updated|\bincorrect\b|\bwrong\b|\berroneous\b",
                                         c.reason or "", re.I) for c in disagreements),
                   "page rank alone does not establish that the lower-ranked page was wrong"))
    changes = [c for c in provenance_conflicts if "change" in c.topic.lower()]
    checks.append(("history reports observations without effective-date claims", bool(changes)
                   and all(first in (c.reason or "") and latest in (c.reason or "")
                           and not re.search(r"current until|effective until|accurate until|not contradictions",
                                             c.reason or "", re.I) for c in changes),
                   "the observed snapshot dates do not prove an exact validity interval"))
    earlier_article = page("/newsroom/earlier-branch-report", "Branch Report",
                           "# Branch Report\n\nJan 4, 2026\n\nAbout Dupaco. It has 9 branch office locations.")
    later_article = page("/newsroom/later-branch-report", "Branch Report",
                         "# Branch Report\n\nFeb 15, 2026\n\nAbout Dupaco. It has 7 branch office locations.")
    article_system = build(submission, [snapshot(first, [earlier_article]), snapshot(latest, [later_article])])
    article_reports = [c for c in article_system.conflicts() if "branch" in c.topic.lower()]
    checks.append(("removed article retains its actual observation snapshot", bool(article_reports)
                   and any({(earlier_article.url, "fixture_" + first), (later_article.url, "fixture_" + latest)}
                           <= {(s.url, s.snapshot_id) for s in c.sources} for c in article_reports),
                   "a January-only article must not be cited as present in March"))
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
    rates_link = page("/rates", "Deposit Rates", "# Certificates\n\n[Certificate rates](/personal/certificates)")
    linked_certificate = page("/personal/certificates", "Certificates", "# Certificates\n\n36-month certificate APY: 3.50%")
    link_system = build(submission, [snapshot(latest, [rates_link, linked_certificate])])
    answer = link_system.answer("Where can I find the 36-month certificate rates?")
    checks.append(("labelled link reaches matching certificate evidence", linked_certificate.url in answer.text,
                   "relative link resolves to the product whose fact matches the requested term"))
    for name, question in [
        ("jumbo certificate link preserves feature checks", "Where can I find the 36-month jumbo certificate rates?"),
        ("unknown certificate link preserves modifier checks", "Where can I find reverse certificate rates?"),
    ]:
        answer = link_system.answer(question)
        checks.append((name, not answer.confident and linked_certificate.url not in answer.text,
                       "a labelled link does not establish an unavailable feature or product"))
    title_only = page("/about/join", "Join", "People who live or work within our charter area may apply.")
    answer = build(submission, [snapshot(latest, [title_only])]).answer("Who can join?")
    checks.append(("title-only match admits substantive passage", "charter area" in answer.text
                   and any(s.url == title_only.url for s in answer.sources),
                   "page title supplies topic even when body has no query word or heading"))
    no_hours = page("/contact", "Branch Hours", "Please contact this office for details.")
    answer = build(submission, [snapshot(latest, [no_hours])]).answer("What are the branch hours?")
    checks.append(("title-only match preserves answer shape", not answer.confident,
                   "an hours title cannot turn prose without times into a schedule"))
    wrong_term = page("/rates", "6-month Certificate Rates", "12-month certificate APY: 6%")
    answer = build(submission, [snapshot(latest, [wrong_term])]).answer("What is the 6-month certificate APY?")
    checks.append(("title-only match preserves numeric qualifiers", not answer.confident,
                   "the title's term and a percentage cannot replace the passage's actual term"))
    # Article-answer predicates share the extractor used for conflict observations.
    count_system = build(submission, [snapshot(first, [earlier_article]),
                                      snapshot(latest, [earlier_article, later_article])])
    trace = {}
    answer = count_system.answer("How many branches does Dupaco have?", _trace=trace)
    checks.append(("article branch answer selects latest dated observation", bool(trace.get("article_answer"))
                   and "7" in answer.text and "2026-02-15" in answer.text
                   and any(s.url == later_article.url and s.snapshot_id == "fixture_" + latest for s in answer.sources),
                   "organization count carries publication date and selected-snapshot source"))
    trace = {}
    count_system.answer("How many branches does Dupaco have in Iowa?", _trace=trace)
    checks.append(("article branch answer does not substitute organization total for state count",
                   not trace.get("article_answer"),
                   "new article-fact path rejects scope it cannot establish; legacy retrieval is separate"))
    tied_article = page("/newsroom/other-branch-report", "Branch Report",
                        "# Branch Report\n\nFeb 15, 2026\n\nAbout Dupaco. It has 8 branch office locations.")
    tied_system = build(submission, [snapshot(latest, [later_article, tied_article])])
    trace = {}
    tied_system.answer("How many branches does Dupaco have?", _trace=trace)
    checks.append(("tied article dates cannot resolve differing organization counts", not trace.get("article_answer"),
                   "same publication date with different values has no automatic latest winner"))
    award_first = page("/newsroom/earlier-forbes-report", "Forbes Recognition Program",
                       "# Forbes Recognition Program\n\nJan 4, 2026\n\nThis was the fourth time Forbes recognized Dupaco for its contribution to the communities that its members call home.")
    award_latest = page("/newsroom/later-forbes-report", "Forbes Recognition Program",
                        "# Forbes Recognition Program\n\nFeb 15, 2026\n\nThis was the fifth time Forbes recognized Dupaco for its contribution to the communities that its members call home.")
    award_system = build(submission, [snapshot(first, [award_first]), snapshot(latest, [award_first, award_latest])])
    award_question = "How many times has Forbes recognized Dupaco?"
    for name, date, expected, source in [
        ("article recognition answer preserves earlier publication", first, "fourth", award_first),
        ("article recognition answer selects latest publication", None, "fifth", award_latest),
    ]:
        trace = {}
        answer = award_system.answer(award_question, date, _trace=trace)
        publication = "2026-01-04" if date else "2026-02-15"
        checks.append((name, bool(trace.get("article_answer")) and expected in answer.text
                       and publication in answer.text
                       and any(s.url == source.url and s.quote and s.quote in source.markdown
                               and expected in s.quote for s in answer.sources),
                       "ordinal, publication date and verbatim supporting quote remain together"))
    trace = {}
    award_system.answer("How many times has Forbes recognized Dupaco for customer service?", _trace=trace)
    checks.append(("article answer rejects unsupported award program", not trace.get("article_answer"),
                   "matching awarder alone cannot establish a different program"))
    cache_system = build(submission, [snapshot(first, [earlier_article])])
    before = cache_system.answer("How many branches does Dupaco have?")
    cache_system.conflicts()
    cache_system.ingest(snapshot(latest, [earlier_article, later_article]))
    trace = {}
    after = cache_system.answer("How many branches does Dupaco have?", _trace=trace)
    checks.append(("article observation cache refreshes after ingest", "9" in before.text
                   and bool(trace.get("article_answer")) and "7" in after.text and "2026-02-15" in after.text,
                   "new snapshot refreshes shared answer/conflict article observations"))
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
        cases = [
            {"id": "sixth-current", "question": question, "must_include": ["4.44%"],
             "must_not_include": ["3.40%"], "category": "stale_trap", "weight": 1.0,
             "expected_sources": [target["url"]]},
            {"id": "sixth-as-of", "question": question, "as_of": previous_date,
             "must_include": ["3.40%"], "must_not_include": ["4.44%"],
             "category": "temporal_as_of", "weight": 1.0, "expected_sources": []},
        ]
        eval_path = Path(temp) / "sixth_eval.jsonl"
        eval_path.write_text("\n".join(json.dumps(case) for case in cases) + "\n")
        output_path = Path(temp) / "harness_results"
        subprocess.run([sys.executable, str(ROOT / "harness/run_eval.py"),
                        "--submission", str(submission.resolve()), "--snapshots", str(copied),
                        "--eval", str(eval_path), "--out", str(output_path)],
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                       capture_output=True, text=True, check=True, timeout=300)
        report = json.loads((output_path / "report.json").read_text())
        return [
            ("sixth snapshot is full", len(snapshots) == len(dirs) + 1 and len(snapshots[-1].pages) == len(snapshots[-2].pages),
             "all prior snapshots copied; October has all latest pages"),
            ("sixth snapshot current rate", "4.44%" in answer.text and source_date(answer, october.name),
             "synthetic APY and October source"),
            ("sixth snapshot preserves prior as-of", "3.40%" in past.text and "4.44%" not in past.text,
             "September APY is unchanged"),
            ("sixth snapshot conflict resolution", any("4.44%" in (c.resolution or "") for c in system.conflicts()),
             "synthetic new value is the conflict resolution"),
            ("sixth snapshot passes actual harness CLI", report["final_score"] == 1.0
             and report["errors"] == 0 and report["stale_trap_hits"] == 0,
             f"run_eval.py --snapshots <full-copy>: score {report['final_score']}, "
             f"errors {report['errors']}, stale traps {report['stale_trap_hits']}"),
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
