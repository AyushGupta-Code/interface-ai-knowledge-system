"""Trace where the supporting evidence of each wrongly refused question disappears.

For every question that should be answered but gets a refusal, this finds the evidence passages in the
chosen snapshot (passages containing the most Answer-key values, using the scorer's contains()) and
replays the four stages of answer() on them:

  1. query     - how the question was read: words, qualifier numbers, answer shape, specific word
  2. page      - did the evidence page hold the right answer shape, and did it survive page coverage?
  3. passage   - which check rejected the passage: shape, qualifier numbers, specific word, low score
  4. ranking   - the passage survived every check but lost to another candidate

Usage: python3 dev/trace_refusals.py [--eval dev/paraphrase_eval.jsonl] [--all] [--quote]
  --all    trace every miss (score < 1), not only refusals
  --quote  print the evidence text (site text: keep the output out of git)
"""
import argparse
import json
import sys
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))
import run_eval  # noqa: E402
from scoring import REFUSAL_RE, contains, score_item  # noqa: E402


def evidence(kb, si, must):
    """Passages of snapshot si holding the most must_include values (ties: most authoritative first)."""
    sol = SimpleNamespace(**type(kb).answer.__globals__)
    found = []
    for pid, p in enumerate(kb.passages):
        if p.snap != si:
            continue
        hay = f"{p.text} {p.url}"
        n = sum(contains(hay, v) for v in must)
        if n:
            found.append((n, pid))
    if not found:
        return []
    top = max(n for n, _ in found)
    pids = [pid for n, pid in found if n == top]
    return sorted(pids, key=lambda pid: (sol.KIND_RANK[kb.passages[pid].kind], kb.passages[pid].url))[:8], top


def verdict(kb, tr, pid):
    """(stage reached, reason) for one evidence passage."""
    sol = SimpleNamespace(**type(kb).answer.__globals__)
    p = kb.passages[pid]
    shape, pcov, best = tr["shape"], tr.get("pcov", {}), tr.get("best_page", 0.0)
    if shape not in kb.pages[p.page][2]:
        return 2, f"page: page holds no '{shape}'-shaped passage"
    cov = pcov.get(p.page, 0.0)
    if best < 0.5:
        return 2, f"page: no page reached coverage 0.5 (best {best:.2f}; this page {cov:.2f})"
    if p.page not in tr.get("pages", ()):
        return 2, f"page: coverage {cov:.2f} < 0.75 x best {best:.2f}"
    if shape not in p.shapes:
        return 3, f"passage: passage is not '{shape}'-shaped (has {sorted(p.shapes - {'any'})})"
    if not sol.numbers_ok(tr["qnums"], p.text):
        return 3, f"passage: qualifier numbers {tr['qnums']} not matched"
    title = kb.pages[p.page][0]
    if tr.get("anchor") and tr["anchor"] not in p.toks and tr["anchor"] not in title:
        return 3, f"passage: specific word '{tr['anchor']}' missing"
    sc = tr.get("score", {}).get(pid)
    if sc is None:
        return 3, "passage: shares no question word"
    if pid not in tr.get("cands", ()):
        return 3, f"passage: score {sc:.2f} < cutoff {tr['cutoff']:.2f} (best {max(tr['score'].values()):.2f})"
    if tr.get("winner") != pid:
        w = kb.passages[tr["winner"]]
        return 4, f"ranking: lost to {w.kind} {w.url.replace('https://www.dupaco.com', '')} (score {tr['score'][tr['winner']]:.2f} vs {sc:.2f})"
    return 5, "won"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", type=Path, default=ROOT / "dev/paraphrase_eval.jsonl")
    ap.add_argument("--snapshots", type=Path, default=ROOT / "snapshots")
    ap.add_argument("--submission", type=Path, default=ROOT / "submission")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--quote", action="store_true")
    args = ap.parse_args()

    items = [json.loads(l) for l in args.eval.read_text().splitlines() if l.strip()]
    kb = run_eval.load_submission(args.submission)
    for s in run_eval.load_snapshots(args.snapshots):
        kb.ingest(s)

    for item in items:
        if item["category"] == "should_refuse":
            continue
        tr = {}
        ans = kb.answer(item["question"], item.get("as_of"), _trace=tr)
        refused = not ans.confident or bool(REFUSAL_RE.search(ans.text or ""))
        res = score_item(item, ans)
        if not (refused or (args.all and res["score"] < 1)):
            continue
        print(f"\n{item['id']}: {item['question']!r} as_of={item.get('as_of')} -> "
              f"{'REFUSED' if refused else 'score %.2f' % res['score']}")
        if tr.get("snap") is None:
            print("  query: date before the first snapshot")
            continue
        print(f"  query: shape={tr['shape']} qnums={tr['qnums']} anchor={tr.get('anchor')} words={sorted(tr['qtoks'])}")
        ev = evidence(kb, tr["snap"], item.get("must_include", []))
        if not ev:
            print("  evidence: none of the Answer-key values is in this snapshot")
            continue
        pids, n = ev
        print(f"  evidence: {len(pids)} passage(s) with {n}/{len(item['must_include'])} key values")
        results = sorted(((verdict(kb, tr, pid), pid) for pid in pids), key=lambda x: -x[0][0])
        for (stage, why), pid in results[:4]:
            p = kb.passages[pid]
            print(f"    [{p.kind} {p.url.replace('https://www.dupaco.com', '')}] {why}")
            if args.quote:
                print(f"        {p.text[:160]!r}")


if __name__ == "__main__":
    main()
