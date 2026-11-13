"""
Credit-union Q&A over dated website snapshots. Decisions D1-D10 are explained in NOTES.md.

ingest():  every page of every snapshot is split into passages (a paragraph, or one table row with
           its column headers and caption) and indexed per snapshot. Nothing is overwritten (D3).
answer():  pick the snapshot by date (D4) -> find passages covering the question -> check the
           question's qualifiers (numbers) against each passage (D9) -> authority first (D6) ->
           answer with every matching row of the winning table (D7), or the winning paragraph.
conflicts(): the same table row (caption + label + column) showing different values (D10).
"""
import math
import re
import sys
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(next(d / "harness" for d in Path(__file__).resolve().parents if (d / "harness" / "contract.py").exists())))
from contract import Answer, Conflict, Snapshot, Source  # noqa: E402

# No digits here: the scorer treats a refusal that states any new number as a non-refusal.
REFUSAL = "I don't know: the website doesn't say. Please contact Dupaco for help."

# ---------------------------------------------------------------------------------------------
# Page types (D6). Lower rank = more authoritative. Order derived in dev/RESEARCH.md §2.
KIND_RANK = {"rates": 0, "product": 1, "other": 2, "promo": 2, "calculator": 3, "article": 4, "file": 5}
ARTICLE_PREFIXES = ("/learn", "/newsroom", "/business/resources", "/resources", "/dupacodaily", "/homebuying-guidance")
PRODUCT_PREFIXES = ("/personal", "/business", "/checking", "/loans", "/savings", "/membership", "/about", "/contact",
                    "/online-and-mobile-banking", "/connect", "/brighttrack", "/shine")


def page_kind(url: str) -> str:
    u = urlparse(url)
    path = u.path.lower().rstrip("/")
    if path in ("/rates", "/business-rates"):
        return "rates"
    if path.startswith(("/calculators", "/business-calculators")):
        return "calculator"
    if path.startswith("/hubfs"):
        return "file"
    if path.startswith(ARTICLE_PREFIXES) or re.match(r"/(19|20)\d\d/", path):
        return "article"
    if path.endswith("-lp") or "offer" in path or "challenge" in path or path in ("/switch-and-earn", "/earn-more"):
        return "promo"
    if path.startswith(PRODUCT_PREFIXES):
        return "product"
    return "other"


MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DATE_LINE = re.compile(r"^\W*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2}), ((?:19|20)\d\d)\b")
BYLINE_DATE = re.compile(r"\|\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2}), ((?:19|20)\d\d)")


def article_date(lines: list[str]) -> str:
    """Publication date of an article as ISO text ('' when none): a standalone date line or a byline."""
    for ln in lines[:60]:
        m = DATE_LINE.match(ln.strip()) or BYLINE_DATE.search(ln)
        if m:
            return f"{m.group(3)}-{MONTHS[m.group(1)[:3].lower()]:02d}-{int(m.group(2)):02d}"
    return ""


# ---------------------------------------------------------------------------------------------
# Text normalisation: member wording -> the site's wording (dev/RESEARCH.md §9), then tokens.
WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "ten": 10,
                "fifteen": 15, "twenty": 20, "thirty": 30}
SYNONYMS = [
    (r"\b(home|house) ?loans?\b", "mortgage"),
    (r"\bcertificates? of deposit\b|\bcds?\b", "certificate"),
    (r"\b(car|vehicle)s?\b", "auto"),
    (r"\bdrive[- ]?(?:through|thru|up)\b", "driveup"),
    (r"\bcredit cards?\b", "visa"),
    (r"\baba\b", "routing"),
    (r"\barms?\b|\badjustable[- ]rate\b", "adjustable"),
    (r"\bbecome a member\b|\bmembership\b", "join"),
    (r"\b(apple|google|samsung) pay\b|\bmobile wallets?\b|\btap to pay\b", "mobile wallet pay"),
    (r"\byield\b", "apy"),
    (r"\b(college|university)\b", "student"),
    (r"\bvto\b", "volunteer time off"),
]
STOP = set("""a an the is are was were be been do does did can could would should will may might of to in on at for
from by with and or not no any all some this that these those there here what which who whom whose when where why how
i me my we our you your it its they them their he she his her dupaco s tell give get please provide like know want
need much many current currently right now today still also just about offer offers have has had am if than then
so too very let us see find info information""".split())


def canonical(text: str) -> str:
    t = text.lower().replace("’", "'")
    t = re.sub(r"\b(" + "|".join(WORD_NUMBERS) + r")\b", lambda m: str(WORD_NUMBERS[m.group(1)]), t)
    for pat, rep in SYNONYMS:
        t = re.sub(pat, rep, t)
    t = re.sub(r"\b(\d+)[- ]?(?:yr|year)s?\b", r"\1 year", t)
    t = re.sub(r"\b(\d+)[- ]?(?:mo|month)s?\b", r"\1 month", t)
    return t


def tokens(text: str) -> set[str]:
    """Content words only; numbers are handled by the qualifier check."""
    out = set()
    for w in re.findall(r"[a-z]+", canonical(text)):
        if w in STOP or len(w) < 2:
            continue
        out.add(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w)
    return out


# ---------------------------------------------------------------------------------------------
# Numbers. Footnote markers are glued onto values ("4.10%2", "APR1"): strip them (RESEARCH §4).
def clean(text: str) -> str:
    text = re.sub(r"(\d%)\d{1,2}\b", r"\1", text)
    text = re.sub(r"\b(APR|APY)\d\b", r"\1", text)
    return text.replace("\\|", "|").replace("\\*", "*")


NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _num(s: str) -> float:
    return float(s.replace(",", ""))


# Calendar dates in a question ("as of May 2026", "2026-05-31") say when, not what: they are not
# qualifiers. Model years ("a 2026 vehicle") are, so only whole date phrases are masked.
DATE_SPAN = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?(?:\s+\d{1,2}(?:st|nd|rd|th)?,?)?\s+(?:19|20)\d\d\b"
    r"|\b(?:19|20)\d\d-\d{1,2}(?:-\d{1,2})?\b|\b(?:as of|in|during) (?:19|20)\d\d\b(?!-)", re.I)


def question_numbers(question: str) -> list[float]:
    """Numbers that qualify the question (terms, amounts, model years); percentages and dates are not qualifiers."""
    out = []
    for m in re.finditer(r"\$?(\d[\d,]*(?:\.\d+)?)(\s*%)?", DATE_SPAN.sub(" ", question)):
        if not m.group(2):
            out.append(_num(m.group(1)))
    return out


def number_spans(text: str) -> tuple[set[float], list[tuple[float, float]]]:
    """Plain numbers in a passage plus the ranges it states (2024-27, $10,000 - $24,999.99, $25,000+, X or less)."""
    nums = {_num(n) for n in NUM.findall(text)}
    spans = []
    for a, b in re.findall(r"\b((?:19|20)\d\d)\s*[-–]\s*(\d{2})\b", text):
        spans.append((float(a), float(a[:2] + b)))
    for a, b in re.findall(r"\$?(\d[\d,]*(?:\.\d+)?)\s*[-–]\s*\$?(\d[\d,]*(?:\.\d+)?)", text):
        if _num(a) <= _num(b):
            spans.append((_num(a), _num(b)))
    for a in re.findall(r"\$?(\d[\d,]*(?:\.\d+)?)\+", text):
        spans.append((_num(a), math.inf))
    for a in re.findall(r"\$?(\d[\d,]*)\s*or less", text, re.I):
        spans.append((0.0, _num(a)))
    return nums, spans


def numbers_ok(qnums: list[float], text: str) -> bool:
    if not qnums:
        return True
    nums, spans = number_spans(text)
    return all(n in nums or any(lo <= n <= hi for lo, hi in spans) for n in qnums)


# ---------------------------------------------------------------------------------------------
@dataclass
class Passage:
    snap: int          # index into self.snaps
    url: str
    title: str
    kind: str
    date: str          # article publication date ('' for non-articles)
    text: str          # cleaned, member-facing text
    toks: frozenset
    table: int = -1    # table id within the page for table rows, -1 otherwise
    label: str = ""    # caption + row label, for conflicts
    cells: tuple = ()  # (header, value) pairs for table rows


def split_page(md: str):
    """Yield (text, table_id, caption, row_cells) for paragraphs and table rows."""
    lines = md.splitlines()
    para, recent, table_id, header = [], [], -1, None
    for ln in lines + [""]:
        s = ln.strip()
        if s.startswith("|"):
            if para:
                yield " ".join(para), -1, "", ()
                para = []
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            if header is None:
                header, table_id = cells, table_id + 1
                continue
            yield s, table_id, " / ".join(recent[-2:]), tuple(zip(header, cells))
            continue
        header = None
        if not s:
            if para:
                yield " ".join(para), -1, "", ()
                para = []
            continue
        if not s.startswith(("![", "[![")):
            para.append(s)
            if len(s) < 80:
                recent.append(s.lstrip("#* ").rstrip("*"))


class KnowledgeBase:
    def __init__(self):
        self.snaps: list[tuple[str, str]] = []         # (snapshot_id, taken_on), oldest first
        self.passages: list[Passage] = []
        self.index: list[dict[str, list[int]]] = []    # per snapshot: token -> passage ids
        self.n_passages: list[int] = []

    # -----------------------------------------------------------------------------------------
    def ingest(self, snapshot: Snapshot) -> None:
        si = len(self.snaps)
        self.snaps.append((snapshot.snapshot_id, snapshot.taken_on))
        index: dict[str, list[int]] = defaultdict(list)
        start = len(self.passages)
        for page in snapshot.pages:
            kind = page_kind(page.url)
            lines = page.markdown.splitlines()
            date = article_date(lines) if kind == "article" else ""
            title = re.sub(r"\s*\|\s*Dupaco.*$", "", page.title or "")
            for text, table, caption, cells in split_page(page.markdown):
                text = clean(text)
                if table >= 0:
                    cells = tuple((clean(h), clean(v)) for h, v in cells)
                    label = " ".join(v for h, v in cells if not re.search(r"\d", v))[:120] or cells[0][1]
                    text = f"{caption + ': ' if caption else ''}" + "; ".join(f"{h}: {v}" if h else v for h, v in cells if v)
                    label = f"{caption} / {label}".strip(" /")
                else:
                    label = ""
                if len(text) < 3:
                    continue
                toks = frozenset(tokens(f"{title} {caption} {text}"))
                p = Passage(si, page.url, title, kind, date, text, toks, table, label, cells)
                pid = len(self.passages)
                self.passages.append(p)
                for t in toks:
                    index[t].append(pid)
        self.index.append(dict(index))
        self.n_passages.append(len(self.passages) - start)

    # -----------------------------------------------------------------------------------------
    def _snapshot_for(self, as_of):
        """D4: newest snapshot on or before as_of; None if as_of precedes every snapshot."""
        if not self.snaps:
            return None
        order = sorted(range(len(self.snaps)), key=lambda i: self.snaps[i][1])
        if not as_of:
            return order[-1]
        dates = [self.snaps[i][1] for i in order]
        k = bisect_right(dates, as_of[:10])
        return order[k - 1] if k else None

    def answer(self, question: str, as_of=None) -> Answer:
        si = self._snapshot_for(as_of)
        if si is None:
            return Answer(text=REFUSAL, confident=False)
        index, n = self.index[si], max(1, self.n_passages[si])
        qtoks = tokens(question)
        idf = {t: math.log(1 + n / (1 + len(index.get(t, ())))) for t in qtoks}
        total = sum(idf.values()) or 1.0
        qnums = question_numbers(question)

        cover = defaultdict(float)
        for t in qtoks:
            for pid in index.get(t, ()):
                cover[pid] += idf[t] / total
        best = max(cover.values(), default=0.0)
        if best < 0.5:
            return Answer(text=REFUSAL, confident=False)
        cands = [pid for pid, c in cover.items() if c >= max(0.5, best - 0.15) and numbers_ok(qnums, self.passages[pid].text)]
        if not cands:
            return Answer(text=REFUSAL, confident=False)

        def rank(pid):
            p = self.passages[pid]
            newest_first = (_neg(p.date) if p.date else "~") if p.kind == "article" else ""
            return (KIND_RANK[p.kind], newest_first, -round(cover[pid], 2), p.url, pid)

        win = self.passages[min(cands, key=rank)]
        sid, taken_on = self.snaps[si]
        if win.table >= 0:
            rows = [self.passages[pid] for pid in sorted(cands)
                    if self.passages[pid].url == win.url and self.passages[pid].table >= 0
                    and cover[pid] >= cover[min(cands, key=rank)] - 1e-9][:12]
            body = "\n".join(f"- {r.text}" for r in rows)
        else:
            body = win.text if len(win.text) <= 600 else win.text[:600].rsplit(" ", 1)[0] + " ..."
        when = f"as of {taken_on}" if as_of else "currently"
        text = f"{win.title or 'Dupaco'} ({when}):\n{body}\nSource: {win.url}"
        return Answer(text=text, sources=[Source(url=win.url, snapshot_id=sid, quote=win.text[:200])])

    # -----------------------------------------------------------------------------------------
    def conflicts(self) -> list[Conflict]:
        """D10: same caption/row/column with different values, within or across snapshots."""
        seen = defaultdict(lambda: defaultdict(list))  # (label, header) -> value -> [(snap, kind, url)]
        for p in self.passages:
            if p.table < 0 or p.kind not in ("rates", "product", "promo", "calculator"):
                continue
            for h, v in p.cells:
                m = re.fullmatch(r"\d+(?:\.\d+)?%", v.strip())
                if m and h:
                    seen[(p.label, h)][v.strip()].append((p.snap, p.kind, p.url))
        out = []
        latest = self._snapshot_for(None)
        for (label, h), vals in seen.items():
            if len(vals) < 2:
                continue
            def strength(item):
                v, where = item
                return max((s == latest, -KIND_RANK[k]) for s, k, _ in where)
            winner = max(vals.items(), key=strength)[0]
            srcs = [Source(url=u, snapshot_id=self.snaps[s][0]) for v in vals for s, _, u in vals[v][:1]]
            out.append(Conflict(topic=f"{label} {h}", values=sorted(vals), sources=srcs, resolution=winner,
                                reason="value on the most authoritative page in the newest snapshot"))
        return out


def _neg(date: str) -> str:
    """Sort key that puts newer ISO dates first."""
    return "".join(chr(0x7F - ord(c)) for c in date)


def build():
    return KnowledgeBase()
