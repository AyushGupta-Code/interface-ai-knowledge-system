"""Research aid: for each eval question, where do the required and the forbidden values live?

Usage: python3 dev/research_map.py [eval.jsonl] > out.txt
Prints only URLs and page types, plus short matching lines, so keep the output out of git.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))
from scoring import contains  # noqa: E402  (the scorer's own matching rule)


def page_type(url: str) -> str:
    u = urlparse(url)
    path = u.path.lower().rstrip("/")
    if u.fragment == "rates" or path in ("/rates", "/business-rates"):
        return "rates"
    if path.startswith(("/calculators", "/business-calculators")):
        return "calculator"
    if path.startswith("/hubfs"):
        return "file"
    if path.startswith(("/learn", "/newsroom", "/business/resources", "/resources", "/dupacodaily")) or re.match(r"/(19|20)\d\d/", path):
        return "article"
    if path.endswith("-lp") or "offer" in path or "challenge" in path:
        return "promo"
    if path.startswith(("/personal", "/business", "/checking", "/loans", "/savings", "/membership", "/about/join", "/mortgage", "/earn-more", "/switch")):
        return "product"
    return "other"


def load():
    snaps = []
    for d in sorted((ROOT / "snapshots").glob("0*")):
        m = json.loads((d / "manifest.json").read_text())
        pages = [(p["url"], page_type(p["url"]), (d / p["file"]).read_text(errors="replace").splitlines()) for p in m["pages"]]
        snaps.append((m["snapshot_id"], m["taken_on"], pages))
    return snaps


def where(token, pages):
    hits = []
    for url, kind, lines in pages:
        for ln in lines:
            if contains(ln, token):
                hits.append((kind, url, ln.strip()[:110]))
                break
    return hits


def main():
    eval_path = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "eval/public_eval.jsonl")
    snaps = load()
    for line in eval_path.read_text().splitlines():
        q = json.loads(line)
        target = snaps[-1]
        if q.get("as_of"):
            target = max((s for s in snaps if s[1] <= q["as_of"]), key=lambda s: s[1], default=None)
        print(f"\n=== {q['id']} [{q['category']}] as_of={q.get('as_of')} -> {target[0] if target else 'NONE'}")
        print(f"Q: {q['question']}")
        for t in q["must_include"]:
            hits = where(t, target[2]) if target else []
            kinds = defaultdict(int)
            for k, _, _ in hits:
                kinds[k] += 1
            print(f"  MUST {t!r}: {dict(kinds) or 'NOT FOUND'}")
            for k, url, ln in hits[:4]:
                print(f"      {k:10} {url}  | {ln}")
        for t in q["must_not_include"]:
            print(f"  NOT  {t!r}:")
            for sid, _, pages in snaps:
                hits = where(t, pages)
                if hits:
                    print(f"      {sid}: " + ", ".join(f"{k}:{urlparse(u).path}" for k, u, _ in hits[:4]) + (f" (+{len(hits) - 4})" if len(hits) > 4 else ""))


if __name__ == "__main__":
    main()
