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
        out.add(stem(w))
    return out


def stem(w: str) -> str:
    """Plural to singular, enough for this site's vocabulary: branches, addresses, policies, rates."""
    if len(w) <= 3 or w.endswith("ss"):
        return w
    if w.endswith(("ches", "shes", "xes", "sses", "zes")):
        return w[:-2]
    if w.endswith("ies"):
        return w[:-3] + "y"
    return w[:-1] if w.endswith("s") else w


# ---------------------------------------------------------------------------------------------
# Answer shape (v2): what the answer must contain for the question to be answered at all.
TIME = re.compile(r"\b\d{1,2}(?::\d\d)?\s*(?:a\.?m\b|p\.?m\b)|\bnoon\b", re.I)
ADDRESS = re.compile(r"\b\d{2,6}\s+(?:[\w.]+\s+){0,4}(?:St|Street|Ave|Avenue|Rd|Road|Ln|Lane|Dr|Drive|Blvd|Way|Hwy|Highway|Ct|Pkwy|Pl|Cir)\b"
                     r"|\b[A-Z]{2},?\s+\d{5}\b")
DATE_TEXT = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+(?:19|20)\d\d\b|\b(?:19|20)\d\d-\d\d-\d\d\b")
RATE_KINDS = ("rates", "product", "promo", "other")   # calculators, articles and files hold the stale rates


def answer_shape(question: str) -> str:
    q = question.lower()
    if re.search(r"\b(link|url|website|web ?page)\b|which page|where (?:on|can i (?:find|see)|do i (?:find|see))", q):
        return "link"
    if re.search(r"\bwhat date\b|\bstill open\b|\bclosing\b|\bshut down\b|\bwhen (?:does|will|did)\b.*\bclose", q):
        return "date"
    if re.search(r"\bhours?\b|what time|\bwhen\b.*\bopen\b", q):
        return "hours"
    if re.search(r"\baddress\b|\bwhere is\b|\blocated\b", q):
        return "address"
    if re.search(r"\bhow many\b|\bnumber of\b", q):
        return "count"
    if re.search(r"\b(fees?|charges?|costs?)\b", q):
        return "fee"
    if re.search(r"\b(rates?|apr|apy|dividends?|interest|yield)\b", q):
        return "rate"
    return "any"


def passage_shapes(kind: str, text: str) -> frozenset:
    """The answer shapes a passage can satisfy; computed once at ingest."""
    s = {"any", "link"}
    if kind in RATE_KINDS and "%" in text:
        s.add("rate")
    if kind in RATE_KINDS and re.search(r"\$\s?\d", text):
        s.add("fee")
    if TIME.search(text):
        s.add("hours")
    if ADDRESS.search(text):
        s.add("address")
    if re.search(r"\d", text):
        s.add("count")
    if DATE_TEXT.search(text):
        s.add("date")
    return frozenset(s)


# Category words never decide whether a passage is about the question's specific subject (D9).
GENERIC = set("""rate interest apr apy dividend yield fee charge cost hour open time address located where branch
location loan account saving member number link url website page dupaco credit union bank month year""".split())


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


def number_spans(text: str):
    """Plain numbers in a passage, plus the year ranges (2024-27) and money ranges
    ($10,000 - $24,999.99, $25,000+, $300,000 or less) it states."""
    nums = {_num(n) for n in NUM.findall(text)}
    years, money = [], []
    for a, b in re.findall(r"\b((?:19|20)\d\d)\s*[-–]\s*(\d{2})\b", text):
        years.append((float(a), float(a[:2] + b)))
    for a, b in re.findall(r"\$(\d[\d,]*(?:\.\d+)?)\s*[-–]\s*\$?(\d[\d,]*(?:\.\d+)?)", text):
        if _num(a) <= _num(b):
            money.append((_num(a), _num(b)))
    for a in re.findall(r"\$(\d[\d,]*(?:\.\d+)?)\+", text):
        money.append((_num(a), math.inf))
    for a in re.findall(r"\$(\d[\d,]*)\s*or less", text, re.I):
        money.append((0.0, _num(a)))
    return nums, years, money


def numbers_ok(qnums: list[float], text: str) -> bool:
    """Each qualifier appears as a number, or (years and dollar amounts only) falls inside a stated range.
    A small number such as the 7 in "7/1 ARM" must appear exactly: "$300,000 or less" doesn't cover it."""
    if not qnums:
        return True
    nums, years, money = number_spans(text)
    for n in qnums:
        if n in nums:
            continue
        spans = years if 1900 <= n <= 2100 else money if n >= 100 else []
        if not any(lo <= n <= hi for lo, hi in spans):
            return False
    return True


# ---------------------------------------------------------------------------------------------
@dataclass
class Passage:
    snap: int          # index into self.snaps
    url: str
    title: str
    kind: str
    date: str          # article publication date ('' for non-articles)
    text: str          # cleaned, member-facing text
    toks: frozenset    # own words + context (heading / table caption); the page title is kept apart
    page: int = -1     # index into self.pages
    shapes: frozenset = frozenset()  # answer shapes this passage can satisfy
    table: int = -1    # table id within the page for table rows, -1 otherwise
    label: str = ""    # caption + row label, for conflicts
    cells: tuple = ()  # (header, value) pairs for table rows


HEADING = re.compile(r"^#{1,6}\s+(.*)$")
BOLD_LABEL = re.compile(r"^\*\*[^*]{1,40}\*\*")                  # "**Lobby** Monday-Thursday: ..."
STATUS = re.compile(r"^(open|closed|open now|closed now)$", re.I)  # live badge, true only at crawl time
LONG = 90                                                          # a line this long is prose, not a list item


def split_page(md: str):
    """Yield (text, table_id, context, row_cells) for the page's passages.

    - A heading is never a passage; it becomes the context of everything under it.
    - Each table row is a passage, with the heading and labels just above the table as context.
    - A long line is a paragraph of its own. A lead-in ending in ':' joins the list after it.
    - Runs of short lines (hours, an address block, bullet items) are grouped into one passage,
      ending at a heading, table, long paragraph or a new bold label ("**Drive-up**").
    """
    lines = md.splitlines()
    heading, labels, group, lead, table_id = "", [], [], "", -1
    out = []

    def flush():
        nonlocal group, lead
        if group:
            out.append(((lead + " " if lead else "") + " · ".join(group), -1, heading, ()))
        group, lead = [], ""

    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("|"):
            flush()
            table_id += 1
            context = " / ".join(x for x in [heading] + labels[-2:] if x)
            header = None
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                i += 1
                if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    continue
                if header is None:
                    header = cells
                    continue
                out.append((lines[i - 1].strip(), table_id, context, tuple(zip(header, cells))))
            labels = []
            continue
        i += 1
        if not s or s.startswith(("![", "[![")) or STATUS.match(s):
            continue
        m = HEADING.match(s)
        if m:
            flush()
            heading, labels = m.group(1).strip("*# "), []
            continue
        if len(s) >= LONG:
            flush()
            if s.endswith(":"):
                lead = s
            else:
                out.append((s, -1, heading, ()))
            continue
        if group and BOLD_LABEL.match(s):
            flush()
        group.append(s)
        if not s.startswith("["):  # link-only lines ("[Apply today](...)") are navigation, not labels
            labels.append(s.strip("*# "))
        if len(group) >= 12:
            flush()
    flush()
    return out


class KnowledgeBase:
    def __init__(self):
        self.snaps: list[tuple[str, str]] = []         # (snapshot_id, taken_on), oldest first
        self.passages: list[Passage] = []
        self.index: list[dict[str, list[int]]] = []    # per snapshot: token -> passage ids
        self.n_passages: list[int] = []
        self.pages: list[tuple[frozenset, frozenset, frozenset]] = []   # (title words, all words, shapes) per page
        self.page_index: list[dict[str, list[int]]] = []     # per snapshot: token -> page ids

    # -----------------------------------------------------------------------------------------
    def ingest(self, snapshot: Snapshot) -> None:
        si = len(self.snaps)
        self.snaps.append((snapshot.snapshot_id, snapshot.taken_on))
        index: dict[str, list[int]] = defaultdict(list)
        page_index: dict[str, list[int]] = defaultdict(list)
        start = len(self.passages)
        for page in snapshot.pages:
            kind = page_kind(page.url)
            lines = page.markdown.splitlines()
            date = article_date(lines) if kind == "article" else ""
            title = re.sub(r"\s*\|\s*Dupaco.*$", "", page.title or "")
            pg = len(self.pages)
            title_toks, page_toks, page_shapes = frozenset(tokens(title)), set(tokens(title)), set()
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
                toks = frozenset(tokens(f"{caption} {text}"))
                shapes = passage_shapes(kind, text)
                p = Passage(si, page.url, title, kind, date, text, toks, pg, shapes, table, label, cells)
                pid = len(self.passages)
                self.passages.append(p)
                page_toks |= toks
                page_shapes |= shapes
                for t in toks:
                    index[t].append(pid)
            self.pages.append((title_toks, frozenset(page_toks), frozenset(page_shapes)))
            for t in page_toks:
                page_index[t].append(pg)
        self.index.append(dict(index))
        self.page_index.append(dict(page_index))
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
        qtoks = tokens(question)
        qnums = question_numbers(question)
        shape = answer_shape(question)

        # Stage A: which pages are about the question (title + all their text) and hold an answer of
        # the right shape (times for an hours question, a % on a rate page for a rate question...).
        pindex = self.page_index[si]
        n_pages = max(1, len({pg for ids in pindex.values() for pg in ids}))
        pidf = {t: math.log(1 + n_pages / (1 + len(pindex.get(t, ())))) for t in qtoks}
        ptotal = sum(pidf.values()) or 1.0
        pcov = defaultdict(float)
        for t in qtoks:
            for pg in pindex.get(t, ()):
                if shape in self.pages[pg][2]:
                    pcov[pg] += pidf[t] / ptotal
        best_page = max(pcov.values(), default=0.0)
        if best_page < 0.5:
            return Answer(text=REFUSAL, confident=False)
        pages = {pg for pg, c in pcov.items() if c >= 0.75 * best_page}

        # Stage B: passages on those pages. Their own words count fully, the page title at half (Q4).
        index, n = self.index[si], max(1, self.n_passages[si])
        idf = {t: math.log(1 + n / (1 + len(index.get(t, ())))) for t in qtoks}
        total = sum(idf.values()) or 1.0
        # D9: the question's most specific word (rarest non-generic word the site uses at all, e.g.
        # "construction", "Mullan") must be in the passage or its page title. Otherwise it's a near miss.
        specific = [t for t in qtoks if t not in GENERIC and index.get(t)]
        anchor = max(specific, key=lambda t: idf[t]) if specific else None
        score = {}
        for t in qtoks:
            for pid in index.get(t, ()):
                p = self.passages[pid]
                if pid in score or p.page not in pages:
                    continue
                if not (shape in p.shapes and numbers_ok(qnums, p.text)):
                    continue
                title_toks = self.pages[p.page][0]
                if anchor and anchor not in p.toks and anchor not in title_toks:
                    continue
                own = sum(idf[x] for x in qtoks & p.toks)
                from_title = sum(idf[x] for x in (qtoks & title_toks) - p.toks)
                score[pid] = (own + 0.5 * from_title) / total
        best = max(score.values(), default=0.0)
        cands = [pid for pid, s in score.items() if s >= max(0.35, best - 0.15)]
        if not cands:
            return Answer(text=REFUSAL, confident=False)

        def rank(pid):
            p = self.passages[pid]
            newest_first = (_neg(p.date) if p.date else "~") if p.kind == "article" else ""
            return (KIND_RANK[p.kind], newest_first, -round(score[pid], 2), p.url, pid)

        win_id = min(cands, key=rank)
        win = self.passages[win_id]
        sid, taken_on = self.snaps[si]
        if win.table >= 0:
            # Every matching row of the winning table, and only that table (D7).
            rows = [self.passages[pid] for pid in sorted(cands)
                    if self.passages[pid].page == win.page and self.passages[pid].table == win.table
                    and score[pid] >= score[win_id] - 1e-9][:12]
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
