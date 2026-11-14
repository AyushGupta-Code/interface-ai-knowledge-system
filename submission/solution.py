"""
Credit-union Q&A over dated website snapshots. Decisions D1-D10 are explained in NOTES.md.

ingest():  every page of every snapshot is split into passages (a paragraph, or one table row with
           its column headers and caption) and indexed per snapshot. Nothing is overwritten (D3).
answer():  pick the snapshot by date (D4) -> find passages covering the question -> check the
           question's qualifiers (numbers) against each passage (D9) -> authority first (D6) ->
           answer with every matching row of the winning table (D7), or the winning paragraph.
conflicts(): the same rate fact (segment + product + tier/term + measure) with different values,
             either across snapshots (history) or across pages in one snapshot (disagreement) (D10).
"""
import math
import re
import sys
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

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
    segments = set(path.strip("/").split("/"))
    for words, kind in (({"rates"}, "rates"), ({"promo", "promotions"}, "promo"),
                        ({"calculator", "calculators"}, "calculator")):
        if segments & words:
            return kind
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
    (r"\bshare certificates?\b", "certificate"),
    (r"\b(home|house) ?loans?\b", "mortgage"),
    (r"\bcertificates? of deposit\b|\bcds?\b", "certificate"),
    (r"\b(car|vehicle)s?\b", "auto"),
    (r"\bdrive[- ]?(?:through|thru|up)(?: windows?)?\b", "driveup"),
    (r"\bcredit cards?\b", "visa"),
    (r"\baba\b", "routing"),
    (r"\barms?\b|\badjustable[- ]rate\b", "adjustable"),
    (r"\bbecome a member\b|\bmembership\b", "join"),
    (r"\b(apple|google|samsung) pay\b|\bmobile wallets?\b|\btap to pay\b", "mobile wallet pay"),
    (r"\byield\b", "apy"),
    (r"\binterest rates?\b", "rate"),     # tables say "Rate"/"APR"; "interest" only matched prose (trace: dup-011)
    (r"\b(college|university)\b", "student"),
    (r"\bvto\b", "volunteer time off"),
    (r"\bshut(?:ting)?(?: down)?\b", "close"),
    (r"\bholding\b", "balance"),
    (r"\b(?:mid|early|late)[- ]?(?=(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b)", ""),
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
    if re.search(r"\bhow (?:do|can|should) (?:i|we) (?:change|update|edit|correct)\b", q):
        return "any"   # "How do I change my address?" asks for a procedure, not an address
    if re.search(r"\b(link|url|website|web ?page)\b|which page|where (?:on|can i (?:find|see)|do i (?:find|see))", q):
        return "link"
    if re.search(r"\bwhat date\b|\bstill (?:open|visit|go|use|bank)\b|\bopen (?:now|anymore)\b|\bclosing\b|\bshut down\b"
                 r"|\bwhen (?:does|will|did)\b.*\bclose", q) and not re.search(r"\binstead\b|\bwhich branch|\bwhere\b", q):
        return "date"
    if re.search(r"\bhours?\b|what time|\bwhen\b.*\bopen\b", q):
        return "hours"
    if re.search(r"\baddress\b|\bwhere is\b|\blocated\b", q):
        return "address"
    if re.search(r"\bhow many\b|\bnumber of\b", q):
        return "count"
    rate_words = re.search(r"\b(rates?|aprs?|apys?|dividends?|interest|yield)\b", q)
    if re.search(r"\bfees?\b", q) or (re.search(r"\b(charges?|costs?)\b", q) and not rate_words):
        return "fee"       # "what APR do you charge" asks for a rate, not a fee
    if rate_words:
        return "rate"
    return "any"


RATE_WORD = re.compile(r"\b(rates?|apr|apy|annual percentage|dividends?|yield|interest)\b", re.I)


def is_rate(text: str, cells=()) -> bool:
    """A % is a rate only when labelled as one: in a table, under a rate/APR/APY/dividend column;
    in prose, in a sentence that names a rate. "Borrow up to 80% of construction costs" is not a rate."""
    if cells:
        return any("%" in v and (_measure(h) or RATE_WORD.search(h)) for h, v in cells)
    return any("%" in sent and RATE_WORD.search(sent) for sent in re.split(r"(?<=[.!?])\s+|\s·\s", text))


def passage_shapes(kind: str, text: str, cells=()) -> frozenset:
    """The answer shapes a passage can satisfy; computed once at ingest."""
    s = {"any", "link"}
    if kind in RATE_KINDS and is_rate(text, cells):
        s.add("rate")
    if kind in RATE_KINDS and re.search(r"\$\s?\d", text):
        s.add("fee")
    if TIME.search(text):
        s.add("hours")
    if ADDRESS.search(text):
        s.add("address")
    if re.search(r"\d|\b(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth) time\b", text, re.I):
        s.add("count")   # "the fifth time Forbes recognized" answers "how many times"
    if DATE_TEXT.search(text):
        s.add("date")
    return frozenset(s)


# Category words never decide whether a passage is about the question's specific subject (D9).
GENERIC = set("""rate interest apr apy dividend yield fee charge cost hour open time address located where branch
location loan account saving member number link url website page dupaco credit union bank month year""".split())
BUNDLE_MARGIN = 0.15   # same margin as the candidate cutoff: passages this close are equally good evidence


_NAME = r"(?!Pay\b|Wallet\b)[A-Z][a-z]+"
PROVIDERS = re.compile(rf"\b((?:{_NAME}, )*{_NAME}),? (or|and) ({_NAME}) (Pay|Wallet)\b")


def expand_providers(text: str) -> str:
    """"Apple, Google or Samsung Pay" -> "Apple Pay, Google Pay or Samsung Pay" in the answer text
    (source quotes keep the site's wording). Only coordinated capitalised names before Pay/Wallet."""
    def fix(m):
        names = m.group(1).split(", ") + [m.group(3)]
        full = [f"{n} {m.group(4)}" for n in names]
        return ", ".join(full[:-1]) + f" {m.group(2)} " + full[-1]
    return PROVIDERS.sub(fix, text)


# Wording words: they say how the member phrased the question, not what it is about, so they can never
# be the specific word (dev/REFUSAL_TRACE.md: between, highest, list... were chosen and caused refusals).
WORDING = set("between highest lowest top best list".split())
# Words naming the kind of answer wanted (a link, a page). They are read by answer_shape(), and are not
# topic words: counting them diluted page coverage ("link to the location finder").
ANSWER_KIND = set("link url website web page list site".split())


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


class TermMonths(float):
    """A term qualifier in months, distinct from balances and model years."""


def question_numbers(question: str) -> list[float]:
    """Numbers that qualify the question (terms, amounts, model years); percentages and dates are not qualifiers."""
    out = []
    question = DATE_SPAN.sub(" ", question)
    # Convert spelled-out terms, not conversational numbers such as "which one".
    question = re.sub(r"\b(" + "|".join(WORD_NUMBERS) + r")\b(?=[ -]+(?:months?|years?|mo|yr)\b)",
                      lambda m: str(WORD_NUMBERS[m.group(1).lower()]), question, flags=re.I)
    for m in re.finditer(r"\$?(\d[\d,]*(?:\.\d+)?)(\s*%)?", question):
        if not m.group(2):
            n = _num(m.group(1))
            unit = re.match(r"[- ]+(months?|years?|mo|yr)\b", question[m.end():], re.I)
            if unit and not m.group(0).startswith("$"):
                n = TermMonths(n * (12 if unit.group(1).lower().startswith(("year", "yr")) else 1))
            out.append(n)
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
        if isinstance(n, TermMonths):
            terms = {float(v) * (12 if unit.lower().startswith(("year", "yr")) else 1)
                     for v, unit in re.findall(r"\b(\d+(?:\.\d+)?)[- ]+(months?|years?|mo|yr)\b", text, re.I)}
            if n not in terms:
                return False
            continue
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
    label: str = ""    # table caption (heading + labels above the table), for conflict identity
    cells: tuple = ()  # (header, value) pairs for table rows
    context: str = ""  # governing section, including for links in ordinary prose


HEADING = re.compile(r"^#{1,6}\s+(.*)$")
BOLD_LABEL = re.compile(r"^\*\*[^*]{1,40}\*\*")                  # "**Lobby** Monday-Thursday: ..."
STATUS = re.compile(r"^(open|closed|open now|closed now)$", re.I)  # live badge, true only at crawl time
LONG = 90                                                          # a line this long is prose, not a list item


def labeled_rate(line: str) -> tuple:
    """Adapt a complete product/measure:percentage line to the table fact interface.

    Ordinary prose, unlabeled percentages and multi-value sentences are not facts.
    Source page classification still controls whether a fact can answer a rate question.
    """
    match = re.fullmatch(
        r"(.+?)\s+(annual percentage yield|annual percentage rate|dividend rate|interest rate|APY|APR|rate)"
        r"\s*:\s*(\d+(?:\.\d+)?\s*%)\s*", line, re.I)
    if not match or not _family_of(match.group(1)):
        return ()
    name, measure, value = match.groups()
    return (("Product", name.strip()), (measure, value))


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
        cells = labeled_rate(s)
        if cells:
            flush()
            table_id += 1
            out.append((s, table_id, heading, cells))
            labels = []
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
        self._fact_index = None
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
        self._fact_index = None    # facts across pages, built on first use after the last ingest
        self._fam_index = None
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
                    text = f"{caption + ': ' if caption else ''}" + "; ".join(f"{h}: {v}" if h else v for h, v in cells if v)
                    label = caption
                else:
                    label = ""
                if len(text) < 3:
                    continue
                toks = frozenset(tokens(f"{caption} {text}"))
                shapes = passage_shapes(kind, text, cells if table >= 0 else ())
                p = Passage(si, page.url, title, kind, date, text, toks, pg, shapes, table, label, cells, caption)
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

    def answer(self, question: str, as_of=None, _trace=None) -> Answer:
        """Prefer selected-snapshot evidence; missing pages may supply dated history."""
        tr = _trace if _trace is not None else {}
        selected = self._snapshot_for(as_of)
        ans = self._answer_snapshot(question, selected, tr)
        if ans.confident and not as_of:
            ans.text = ans.text.replace(f"(as of {self.snaps[selected][1]}):", "(currently):", 1)
        if ans.confident or selected is None:
            return ans
        # A failed eligibility/shape/qualifier/ranking check is not absence of evidence.
        # Keep this deliberately conservative: plausible current subject pages block history.
        if tr.get("best_page", 0) >= 0.5:
            return ans
        subject = tokens(question) - GENERIC - WORDING - ANSWER_KIND
        current_pages = {p.page for p in self.passages if p.snap == selected}
        if subject and any(subject <= self.pages[pg][1] for pg in current_pages):
            # A withdrawal or unavailable-product notice need not have the requested shape.
            return ans
        qfam = _family_of(canonical(question)) if answer_shape(question) == "rate" else ""
        if qfam and any(p.snap == selected and _family_of(p.text) == qfam
                        and re.search(r"withdrawn|discontinued|no longer (?:available|offered|published)", p.text, re.I)
                        for p in self.passages):
            return ans
        if qfam and any(f == qfam or CATEGORY.get(f) == qfam for f in self._family_index()[selected][0]):
            return ans
        limit = self.snaps[selected][1]
        for old in sorted((i for i, (_, d) in enumerate(self.snaps) if d < limit),
                          key=lambda i: self.snaps[i][1], reverse=True):
            past_trace = {}
            past = self._answer_snapshot(question, old, past_trace)
            if not past.confident:
                continue
            win = self.passages[past_trace["winner"]]
            # Never resurrect an earlier version when any later version of its page exists,
            # including withdrawal notices or a different published tier/measure.
            if any(p.url == win.url and self.snaps[old][1] < self.snaps[p.snap][1] <= limit
                   for p in self.passages):
                continue
            if win.kind not in ("rates", "product", "other"):
                continue
            page_text = " ".join(p.text for p in self.passages if p.page == win.page)
            if re.search(r"\b(expired|withdrawn|discontinued|superseded)\b|no longer (?:available|offered|published)"
                         r"|\bexpires?\b|\bvalid (?:until|through)\b|\bavailable until\b"
                         r"|offer (?:ended|ends)|promotion (?:ended|ends)", page_text, re.I):
                continue
            observed = self.snaps[old][1]
            body = past.text.split("\n", 1)[-1].rsplit("\nSource:", 1)[0]
            tr.update(past_trace, historical=True, selected_snapshot=selected)
            return Answer(text=f"The selected snapshot ({limit}) doesn't publish this information. "
                          f"Last observed on {observed}:\n{body}\n"
                          f"I can't confirm the current value.\nSource: {win.url}", sources=past.sources)
        return ans

    def _answer_snapshot(self, question: str, si, _trace=None) -> Answer:
        """_trace: optional dict filled with every stage's intermediate results (dev/trace_refusals.py)."""
        tr = _trace if _trace is not None else {}
        tr["snap"] = si
        if si is None:
            return Answer(text=REFUSAL, confident=False)
        qtoks = tokens(question) - ANSWER_KIND
        qnums = question_numbers(question)
        shape = answer_shape(question)
        tr.update(qtoks=qtoks, qnums=qnums, shape=shape)
        if not qtoks:
            return Answer(text=REFUSAL, confident=False)
        if shape == "link":
            linked = self._labeled_link(question, si, tr)
            if linked is not None:
                return linked

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
        tr.update(pcov=dict(pcov), best_page=best_page)
        if best_page < 0.5:
            return Answer(text=REFUSAL, confident=False)

        # Stage B: passages on those pages. Their own words count fully, the page title at half (Q4).
        index, n = self.index[si], max(1, self.n_passages[si])
        idf = {t: math.log(1 + n / (1 + len(index.get(t, ())))) for t in qtoks}
        total = sum(idf.values()) or 1.0
        # D9: the question's most specific word (rarest non-generic word the site uses at all, e.g.
        # "construction", "Mullan") must be in the passage or its page title. Otherwise it's a near miss.
        specific = [t for t in qtoks if t not in GENERIC and t not in WORDING and index.get(t)]
        anchor = max(specific, key=lambda w: idf[w]) if specific else None
        tr.update(anchor=anchor, idf=idf)

        # D9 for rates, by product family (replaces the one-word veto when the question names a family):
        # the rate must come from a row of that family (Share Savings, not the Money Market on the same
        # page); question words that this family's rows use must be in the row (jumbo, platinum, share);
        # a modifier or feature that only a sibling product has ("introductory" on the Rewards Visa), or
        # that no row of the family has ("reverse", "interest-only" mortgage, "Unicorn" Savings), refuses.
        fam_rows, required = None, set()
        qfam = _family_of(canonical(question)) if shape == "rate" else ""
        tr["family"] = qfam
        if shape == "rate" and not qfam:
            # A rate for a product the site has no rate family for (construction, payday, student loans).
            return Answer(text=REFUSAL, confident=False)
        if qfam:
            by_family, vocab = self._family_index()[si]
            group = [f for f in by_family if f == qfam or CATEGORY.get(f) == qfam]
            fam_rows = {pid for f in group for pid in by_family[f]}
            own = set().union(*(vocab[f] for f in group)) if group else set()
            siblings = set().union(*(vocab[f] for f in by_family if CATEGORY.get(f, f) == CATEGORY.get(qfam, qfam)
                                     and f not in group)) - own
            content = qtoks - GENERIC - WORDING - DEFAULT_TIER
            modifier = _modifier(canonical(question), qfam)
            tr.update(family=qfam, modifier=modifier, sibling_words=sorted(content & siblings))
            if not fam_rows or (modifier and modifier not in own) or content & siblings:
                return Answer(text=REFUSAL, confident=False)
            required, anchor = content & own, None
            tr.update(anchor=sorted(required))

        def search(pages):
            score = {}
            candidates = {pid for t in qtoks for pid in index.get(t, ())}
            title_pages = {pg for pg in pages if qtoks & self.pages[pg][0]}
            candidates.update(pid for pid, p in enumerate(self.passages) if p.page in title_pages)
            for pid in sorted(candidates):
                p = self.passages[pid]
                if pid in score or p.page not in pages:
                    continue
                if not (shape in p.shapes and numbers_ok(qnums, p.text)):
                    continue
                title_toks = self.pages[p.page][0]
                if anchor and anchor not in p.toks and anchor not in title_toks:
                    continue
                if fam_rows is not None and (pid not in fam_rows or not required <= p.toks | title_toks):
                    continue
                own = sum(idf[x] for x in qtoks & p.toks)
                from_title = sum(idf[x] for x in (qtoks & title_toks) - p.toks)
                score[pid] = (own + 0.5 * from_title) / total
            best = max(score.values(), default=0.0)
            cutoff = max(0.35, best - 0.15)
            return score, cutoff, [pid for pid, sc in score.items() if sc >= cutoff]

        # The best-covered pages first; if none of them holds a passing passage, every page that still
        # covers half the question (a refusal only when nothing on the site passes the checks).
        pages = {pg for pg, c in pcov.items() if c >= 0.75 * best_page}
        score, cutoff, cands = search(pages)
        if not cands:
            pages = {pg for pg, c in pcov.items() if c >= 0.5}
            score, cutoff, cands = search(pages)
        tr.update(pages=pages, score=score, cutoff=cutoff, cands=cands)
        if not cands:
            return Answer(text=REFUSAL, confident=False)

        def rank(pid):
            # Authority first (D6); then a page whose title names the question's subject (category words
            # like 'branch' or 'rate' don't count); then, among
            # articles, the newest; then the passage's own score.
            p = self.passages[pid]
            about = round(sum(idf[w] for w in (qtoks - GENERIC) & self.pages[p.page][0]) / total, 2)
            newest_first = (_neg(p.date) if p.date else "~") if p.kind == "article" else ""
            return (KIND_RANK[p.kind], -about, newest_first, -round(score[pid], 2), p.url, pid)

        win_id = min(cands, key=rank)
        tr["winner"] = win_id
        win = self.passages[win_id]
        sid, taken_on = self.snaps[si]
        sources = [Source(url=win.url, snapshot_id=sid, quote=win.text[:200])]
        if win.table >= 0:
            # Every matching row of the winning table, and only that table (D7).
            row_ids = [pid for pid in sorted(cands)
                       if self.passages[pid].page == win.page and self.passages[pid].table == win.table
                       and score[pid] >= score[win_id] - 1e-9][:12]
            if fam_rows:
                # A category question ("your credit cards") spans several tables and pages (personal and
                # business cards): add the family's other rows that are as strong as the winner, from rate
                # and product pages, once per fact.
                by_pid, by_fact = self._fact_index_get()
                seen = {(by_pid.get(pid), tuple(sorted(by_fact[by_pid[pid]][self.passages[pid].url].items())))
                        for pid in row_ids if pid in by_pid}
                more = sorted((pid for pid in score if pid in fam_rows and pid not in row_ids
                               and self.passages[pid].kind in ("rates", "product")
                               and score[pid] >= score[win_id] - 1e-9),
                              key=lambda pid: (KIND_RANK[self.passages[pid].kind], self.passages[pid].url, pid))
                for pid in more:
                    if pid not in by_pid:
                        continue
                    fact = (by_pid[pid], tuple(sorted(by_fact[by_pid[pid]][self.passages[pid].url].items())))
                    if fact not in seen and len(row_ids) < 12:
                        seen.add(fact)
                        row_ids.append(pid)
            body = "\n".join(f"- {self.passages[pid].text}" for pid in row_ids)
            sources += [Source(url=u, snapshot_id=sid) for u in self._same_fact_pages(row_ids, win.url)]
            for u in dict.fromkeys(self.passages[pid].url for pid in row_ids):
                if u not in {src.url for src in sources}:
                    sources.append(Source(url=u, snapshot_id=sid))
        else:
            # Evidence bundle: the page's other passages that pass every check and score close to the
            # winner, in page order, so an answer split over adjacent paragraphs (a program and its
            # amount, a closure and its date) is not cut in half. Same page only.
            near = sorted(pid for pid in score if self.passages[pid].page == win.page
                          and self.passages[pid].table < 0 and score[pid] >= score[win_id] - BUNDLE_MARGIN)
            near = ([win_id] + [pid for pid in near if pid != win_id])[:3]
            parts = [self.passages[pid].text for pid in sorted(near)]
            body = " ... ".join(parts)
            body = body if len(body) <= 900 else body[:900].rsplit(" ", 1)[0] + " ..."
        body = expand_providers(body)
        when = f"as of {taken_on}"
        text = f"{win.title or 'Dupaco'} ({when}):\n{body}\nSource: {win.url}"
        return Answer(text=text, sources=sources)

    def _labeled_link(self, question: str, si: int, trace: dict):
        """Return actual destinations supported by link labels/sections and target evidence."""
        family = _family_of(canonical(question))
        subject = tokens(question) - GENERIC - WORDING - ANSWER_KIND - {"use", "find", "see"}
        if not subject:
            return None
        by_url = defaultdict(list)
        for pid, p in enumerate(self.passages):
            if p.snap == si:
                by_url[urlparse(p.url)._replace(fragment="").geturl().rstrip("/")].append(pid)
        family_rows = set()
        required = set()
        if family:
            families, vocab = self._family_index()[si]
            group = [f for f in families if f == family or CATEGORY.get(f) == family]
            family_rows = {pid for f, pids in families.items()
                           if f == family or CATEGORY.get(f) == family for pid in pids}
            scope = re.search(r"\b(personal|business)\b", question, re.I)
            if scope:
                by_pid, _ = self._fact_index_get()
                family_rows = {pid for pid in family_rows if pid in by_pid
                               and by_pid[pid][1][0].lower() == scope.group(1).lower()}
            own = set().union(*(vocab[f] for f in group)) if group else set()
            siblings = set().union(*(vocab[f] for f in families
                if CATEGORY.get(f, f) == CATEGORY.get(family, family) and f not in group)) - own
            content = tokens(question) - GENERIC - WORDING - DEFAULT_TIER - ANSWER_KIND
            modifier = _modifier(canonical(question), family)
            if scope:
                content.discard(scope.group(1).lower())
                if modifier == scope.group(1).lower():
                    modifier = ""
            if not family_rows or (modifier and modifier not in own) or content & siblings:
                return Answer(text=REFUSAL, confident=False)
            required = content & own
        links = []
        for pid, p in enumerate(self.passages):
            if p.snap != si or p.kind not in ("rates", "product", "other"):
                continue
            for label, href in re.findall(r"\[([^\[\]]+)\]\(([^\s)]+)\)", p.text):
                destination = urljoin(p.url, href)
                if urlparse(destination).scheme not in ("http", "https"):
                    continue
                context = label + " " + p.context
                if family:
                    if _family_of(context) != family:
                        continue
                elif not subject <= tokens(context):
                    continue
                target = urlparse(destination)._replace(fragment="").geturl().rstrip("/")
                targets = by_url.get(target, [])
                if family:
                    targets = [i for i in targets if i in family_rows
                               and required <= self.passages[i].toks | self.pages[self.passages[i].page][0]
                               and numbers_ok(question_numbers(question), self.passages[i].text)]
                if not targets:
                    continue  # No guessing destinations or following external sites.
                target_id = min(targets)
                shown = p.context or label
                links.append((KIND_RANK[p.kind], destination, pid, target_id, shown))
        if not links:
            return Answer(text=REFUSAL, confident=False) if family else None
        chosen, seen = [], set()
        for _, destination, pid, target_id, label in sorted(links):
            if destination not in seen:
                seen.add(destination)
                chosen.append((destination, pid, target_id, label))
            if len(chosen) == 3:
                break
        sources = []
        for _, pid, target_id, _ in chosen:
            for i in (pid, target_id):
                p = self.passages[i]
                if p.url not in {s.url for s in sources}:
                    sources.append(Source(url=p.url, snapshot_id=self.snaps[si][0], quote=p.text[:200]))
        trace.update(winner=chosen[0][1], link_answer=True)
        return Answer(text="Published links:\n" + "\n".join(
            f"- {label}: {url}" for url, _, _, label in chosen), sources=sources)

    def _fact_index_get(self):
        """pid -> (snap, fact key), and (snap, fact key) -> url -> measure -> value; built once."""
        if self._fact_index is None:
            by_pid, by_fact = {}, defaultdict(lambda: defaultdict(dict))
            for key, m, snap, kind, url, v, _, pid in self._facts(with_pid=True):
                by_pid[pid] = (snap, key)
                by_fact[(snap, key)][url][m] = v
            self._fact_index = (by_pid, by_fact)
        return self._fact_index

    def _family_index(self):
        """Per snapshot: product family -> its rate-row passage ids, and family -> words its rows use."""
        if getattr(self, "_fam_index", None) is None or len(self._fam_index) != len(self.snaps):
            fams = [(defaultdict(set), defaultdict(set)) for _ in self.snaps]
            for key, m, snap, kind, url, v, _, pid in self._facts(with_pid=True):
                by_family, vocab = fams[snap]
                by_family[key[1]].add(pid)
                vocab[key[1]] |= self.passages[pid].toks
            self._fam_index = fams
        return self._fam_index

    def _same_fact_pages(self, row_ids, cited: str, limit: int = 5) -> list[str]:
        """Other rate and product pages in the same snapshot that state every quoted row as the same
        fact (same product, tier/term and values, by the conflict identity of D10)."""
        by_pid, by_fact = self._fact_index_get()
        common = None
        for pid in row_ids:
            if pid not in by_pid:
                return []
            pages = by_fact[by_pid[pid]]
            mine = pages.get(self.passages[pid].url, {})
            same = {u for u, vals in pages.items() if vals == mine}
            common = same if common is None else common & same
        ok = [u for u in (common or ()) if u != cited and page_kind(u) in ("rates", "product")]
        return sorted(ok, key=lambda u: (KIND_RANK[page_kind(u)], u))[:limit]

    # -----------------------------------------------------------------------------------------
    def conflicts(self) -> list[Conflict]:
        """D10: precise facts inside, readable reports outside.

        Inside, a fact is one table row's identity (segment + product + tier/term/model-year band),
        compared measure by measure, so balance tiers, APR vs APY and personal vs business are never
        compared with each other (see _fact_conflicts). Outside, the fact-level findings of one product
        and one kind are grouped into a single report ("Personal Home Loan rates (changed over time)"),
        one value line per row, so a single rate-sheet update reads as one event, not twenty rows.
        """
        groups = {}
        for f in self._fact_conflicts():
            groups.setdefault((f["kind"], f["segment"], f["group"]), []).append(f)
        reports = []
        for (kind, segment, group), fs in groups.items():
            values = [f"{f['row']}: {v}" for f in fs for v in f["values"]]
            sources, seen = [], set()
            for f in fs:
                for src in f["sources"]:
                    if (src.url, src.snapshot_id) not in seen:
                        seen.add((src.url, src.snapshot_id))
                        sources.append(src)
            pages = sorted({p for f in fs for p in f["pages"]})
            if kind == "history":
                label = "Change"
                reason = "Change observations: " + "; ".join(
                    f"{f['row']}: " + ", ".join(f"{value} on {date} at {url}"
                                                 for date, url, value in f["observations"])
                    for f in fs)
            else:
                label = "Disagreement"
                reason = "Disagreement observations: " + "; ".join(
                    f"{f['row']}: " + ", ".join(
                        f"on {date}, {u1} shows {v1} while {u2} shows {v2}"
                        for date, u1, v1, u2, v2 in f["observations"])
                    for f in fs)
            reason += "; " + "; ".join(
                f"{f['row']}: latest observation {f['last_date']} at {f['last_url']}; "
                + ("resolution follows source authority within that snapshot"
                   if f['resolution'] is not None else "absent from latest snapshot; current value unconfirmed")
                for f in fs)
            reports.append(((kind, tuple(values)), Conflict(
                topic=f"{segment} {group} rates ({label})", values=values, sources=sources,
                resolution="; ".join(f"{f['row']}: {f['resolution']}" for f in fs
                                     if f['resolution'] is not None) or None, reason=reason)))
        return _merge_copies(reports) + self._article_conflicts()

    def _article_conflicts(self) -> list[Conflict]:
        """D10 for article text: organisation-wide counts that newsroom articles state differently.

        Each observation preserves value, publication date, snapshot and source. Different publication
        dates are not proof that an article was erroneous. Two bounded patterns: branch-office counts,
        and "the Nth time <awarder> recognized
        Dupaco" (kept apart per award program, taken from the article title)."""
        newest = {}                        # url -> passages of its newest snapshot
        for p in self.passages:
            if p.kind == "article" and p.date:
                if p.url not in newest or self.snaps[p.snap][1] > self.snaps[newest[p.url][0].snap][1]:
                    newest[p.url] = [p]
                elif self.snaps[p.snap][1] == self.snaps[newest[p.url][0].snap][1]:
                    newest[p.url].append(p)
        obs = defaultdict(dict)            # fact -> url -> (date, value)
        for url, ps in newest.items():
            for p in ps:
                for m in BRANCH_COUNT.finditer(p.text):
                    obs[("Number of Dupaco branch offices", "")][url] = (p.date, m.group(1), p.snap)
                for m in TIMES_RECOGNIZED.finditer(p.text):
                    program = re.sub(r"\s+", " ", p.title.lower()).strip()
                    obs[(f"Times {m.group(2)} has recognized Dupaco", program)][url] = (p.date, m.group(1).lower(), p.snap)
        out = []
        for (topic, program), seen in obs.items():
            dated = sorted(seen.items(), key=lambda kv: kv[1][0], reverse=True)   # newest article first
            values = list(dict.fromkeys(v for _, (_, v, _) in dated))
            if len(values) < 2:
                continue
            first = {}
            for url, (date, v, snap) in dated:
                first.setdefault(v, (date, url, snap))
            out.append(Conflict(
                topic=f"{topic}{' (' + program + ')' if program else ''} (newsroom articles disagree)",
                values=values,
                sources=[Source(url=first[v][1], snapshot_id=self.snaps[first[v][2]][0]) for v in values],
                resolution=values[0] if first[values[0]][2] == self._snapshot_for(None) else None,
                reason="dated observations: " + "; ".join(f"{v} in the article of {first[v][0]}" for v in values)
                       + f"; newest article found, {first[values[0]][0]}, says {values[0]}; "
                       "publication dates do not establish exact change dates or historical accuracy"))
        return out

    def _fact_conflicts(self):
        """Fact-level findings: one dict per (fact, kind) with its values, resolution and evidence."""
        order = sorted(range(len(self.snaps)), key=lambda i: self.snaps[i][1])
        age = {s: len(order) - 1 - i for i, s in enumerate(order)}    # 0 = newest snapshot
        facts = defaultdict(list)          # fact -> [(snap, rank, url, measure, value)]
        labels = {}                        # fact -> (segment, group, row), worded as the newest, most authoritative row
        for key, measure, snap, kind, url, value, label in self._facts():
            facts[key].append((snap, KIND_RANK[kind], url, measure, value))
            rank = (KIND_RANK[kind], age[snap])
            if key not in labels or rank < labels[key][0]:
                labels[key] = (rank, label)
        for key, obs in facts.items():
            if min(r for _, r, *_ in obs) > KIND_RANK["product"]:
                continue                   # identity is trusted only when a rate or product page states it
            segment, group, row = labels[key][1]
            base = {"segment": segment, "group": group, "row": row}
            pages = defaultdict(lambda: defaultdict(dict))   # (rank, url) -> snap -> measure -> value
            for snap, rank, url, m, v in obs:
                pages[(rank, url)][snap][m] = v
            ref = min(pages, key=lambda p: (p[0], -len(pages[p]), p[1]))
            present = [s for s in order if any(s in pages[p] for p in pages)]
            def best(s):                   # most authoritative page showing the fact in snapshot s
                p = ref if s in pages[ref] else min(q for q in pages if s in pages[q])
                return p, pages[p][s]
            cur_page, cur = best(present[-1])
            cur_src = Source(url=cur_page[1], snapshot_id=self.snaps[present[-1]][0])
            resolution = _show(cur) if present[-1] == order[-1] else None
            base.update(last_date=self.snaps[present[-1]][1], last_url=cur_page[1])
            # 1) history on the reference page
            changes = []
            for s in order:
                v = pages[ref].get(s)
                if v is not None and (not changes or _differs(v, changes[-1][1])):
                    changes.append((s, v))
            if len(changes) > 1:
                yield dict(base, kind="history", values=[_show(v) for _, v in changes], resolution=resolution,
                           sources=[Source(url=ref[1], snapshot_id=self.snaps[s][0]) for s, _ in changes] + [cur_src],
                           observations=[(self.snaps[s][1], ref[1], _show(v)) for s, v in changes],
                           pages=[urlparse(ref[1]).path], dates=[self.snaps[s][1] for s, _ in changes[1:]])
            # 2) disagreement inside one snapshot
            dissent, refs = {}, set()      # (url, shown value) -> newest snapshot showing it
            for s in present:
                (_, ref_url), ref_v = best(s)
                for (rank, url), snaps in pages.items():
                    v = snaps.get(s)
                    if v is not None and url != ref_url and _differs(v, ref_v):
                        dissent[(url, _show(v))] = (s, ref_url, _show(ref_v))
                        refs.add(_show(ref_v))
            values = [_show(cur)] + sorted(({v for _, v in dissent} | refs) - {_show(cur)})
            if dissent and len(values) > 1:
                yield dict(base, kind="disagreement", values=values, resolution=resolution,
                           sources=[cur_src] + [Source(url=u, snapshot_id=self.snaps[s][0])
                               for (url, _), (s, ref_url, _) in sorted(dissent.items()) for u in (ref_url, url)],
                           observations=[(self.snaps[s][1], ref_url, ref_v, url, v)
                                         for (url, v), (s, ref_url, ref_v) in sorted(dissent.items())],
                           pages=[urlparse(cur_page[1]).path], stale=sorted({urlparse(u).path for u, _ in dissent}))

    def _facts(self, with_pid=False):
        """Yield (fact key, measure, snap, kind, url, value, (segment, group, row)) per rate cell of each table row."""
        tables = defaultdict(list)
        pids = {id(p): i for i, p in enumerate(self.passages)} if with_pid else {}
        for p in self.passages:
            if p.table >= 0 and p.kind != "file" and p.cells:
                tables[(p.snap, p.url, p.table)].append(p)
        parsed, named = [], defaultdict(set)
        for (snap, url, _), rows in tables.items():
            if not any(_measure(h) for h, _ in rows[0].cells):
                continue
            caption = rows[0].label
            segment = "Business" if "/business" in url.lower() or "business" in caption.lower() else "Personal"
            years = {}                     # model-year label -> position in this table (0 = newest years)
            items = []
            for p in rows:
                name, quals, shown, vals = "", [], [], {}
                for h, v in p.cells:
                    m = _measure(h)
                    if not v or IGNORED_COL.search(h):
                        continue
                    if m:
                        if _value(v) is not None:
                            vals[m] = _value(v)
                    elif PRODUCT_COL.fullmatch(h.strip().lower()):
                        name = v
                    elif MODEL_YEAR.search(v):
                        quals.append(f"model-year tier {years.setdefault(v, len(years))}")
                        shown.append(v)
                    else:
                        quals.append(_qual(v))
                        shown.append(v)
                if name.lower().startswith("business ") or "(business)" in name.lower():
                    segment = "Business"
                name = re.sub(r"\s*\(business\)|^business\s+", "", name, flags=re.I).strip(" —-")
                if vals:
                    items.append((name, tuple(quals), " ".join(shown), vals, id(p)))
            if not items:
                continue
            family = _family(rows, items, caption, url)
            if not family:
                continue
            for name in {n for n, *_ in items if n}:
                named[(segment, family, frozenset(q for n, q, *_ in items if n == name))].add(name)
            parsed.append((snap, rows[0].kind, url, segment, family, items))
        for snap, kind, url, segment, family, items in parsed:
            if not any(n for n, *_ in items):
                # No product column: borrow the name of the one named table with the same tiers.
                same = named.get((segment, family, frozenset(q for _, q, *_ in items)), set())
                if len(same) == 1:
                    items = [(next(iter(same)),) + it[1:] for it in items]
                elif family in NAMED_FAMILIES:
                    continue               # several products share these tiers: identity unknown
            for name, quals, shown, vals, pkey in items:
                key = (segment, family, name.lower(), quals)
                # Report grouping: named deposit products report on their own (Share Savings, Money
                # Market...); loans, certificates and IRAs report per family, the name joining the row.
                if family in NAMED_FAMILIES and name:
                    label = (segment, _product(name, family), shown)
                else:
                    label = (segment, family, " ".join(x for x in [name, shown] if x))
                for m, v in vals.items():
                    if with_pid:
                        yield key, m, snap, kind, url, v, label, pids[pkey]
                    else:
                        yield key, m, snap, kind, url, v, label


# Conflict identity helpers (D10) ---------------------------------------------------------------
def _merge_copies(reports: list) -> list:
    """One rate sheet published under several products (personal and business certificates) changes
    as one event: reports with the same kind and identical value lines become one report."""
    merged = {}
    for key, c in reports:
        if key in merged:
            first = merged[key]
            first.topic = first.topic.replace(" rates (", " rates; " + c.topic.split(" rates (")[0] + " rates (", 1)
            seen = {(src.url, src.snapshot_id) for src in first.sources}
            first.sources += [src for src in c.sources if (src.url, src.snapshot_id) not in seen]
        else:
            merged[key] = c
    return list(merged.values())


PRODUCT_COL = re.compile(r"account type|ira type|card type|product")
IGNORED_COL = re.compile(r"min\.? to|points|payment", re.I)
MODEL_YEAR = re.compile(r"model year|(?:19|20)\d\d\s*[-–]\s*(?:\d\d){1,2}\b", re.I)
NAMED_FAMILIES = {"Savings", "Checking", "Money Market", "Health Savings Account"}
FAMILIES = [
    (r"\bira\b|roth|traditional:", "IRA"),
    (r"certificate", "Certificate"),
    (r"auto|motorcycle|vehicle", "Auto & Motorcycle Loan"),
    (r"boat|\brv\b", "Boat & RV Loan"),
    (r"\batv\b|snowmobile|jet ski", "ATV, Snowmobile & Jet Ski Loan"),
    (r"personal loan", "Personal Loan"),
    (r"home improvement", "Home Improvement Loan"),
    (r"heloc|line of credit", "Home Equity Line of Credit"),
    (r"home equity", "Home Equity Loan"),
    (r"refinanc", "Home Loan Refinance"),
    (r"home loan|mortgage|homebuying|purchase:", "Home Loan"),
    (r"rewards visa", "Rewards Visa"),
    (r"platinum visa", "Platinum Visa"),
    (r"credit card|visa", "Credit Card"),
    (r"money market", "Money Market"),
    (r"health savings|\bhsa\b", "Health Savings Account"),
    (r"checking", "Checking"),
    (r"savings", "Savings"),
]


# Words asking for a product's ordinary rate rather than a special one ("standard purchase APR"): they
# never name a feature, so they are not checked against sibling products (the Rewards Visa's tier
# happens to be called "Standard").
DEFAULT_TIER = set("standard regular normal basic ongoing purchase".split())

# Article facts for conflicts (D10). Organisation-wide statements only: "It has ... 22 branch office
# locations" (the newsroom boilerplate) and "Dupaco now operates 22 branches", not "Dupaco's 18 branches"
# in a biography.
BRANCH_COUNT = re.compile(r"\b(?:has|operates)\b[^.]{0,60}?\b(\d{1,3}) (?:branch office locations|branches)\b")
TIMES_RECOGNIZED = re.compile(r"\b(?:was|is) the (first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth) "
                              r"time ([A-Z][\w.]+) (?:has )?(?:recognized|named|ranked)\b", re.I)

# Families that name a whole category in a question ("credit card rates" -> every card).
CATEGORY = {"Platinum Visa": "Credit Card", "Rewards Visa": "Credit Card",
            "Home Loan Refinance": "Home Loan", "Home Equity Loan": "Home Loan",
            "Home Equity Line of Credit": "Home Loan", "Home Improvement Loan": "Home Loan"}


def _modifier(question: str, family: str) -> str:
    """The word right before the family's name in the question ("reverse mortgage" -> "reverse"),
    or '' if it is a number, a stop word or a category word."""
    for pat, fam in FAMILIES:
        if fam == family:
            m = re.search(pat, question, re.I)
            if not m:
                return ""
            before = re.findall(r"[a-z]+", question[:m.start()].lower())
            w = stem(before[-1]) if before else ""
            return "" if not w or w in STOP or w in GENERIC or w in WORDING or w in DEFAULT_TIER or len(w) < 2 else w
    return ""


def _family_of(text: str) -> str:
    for pat, fam in FAMILIES:
        if re.search(pat, text, re.I):
            return fam
    return ""


def _family(rows, items, caption: str, url: str) -> str:
    """Product family, from the strongest evidence first: the product column, the table's own
    shape (a deposit table whose rows are terms is a certificate table), the caption parts
    nearest the table, the row labels, and finally the URL."""
    for name, *_ in items:
        if name and _family_of(name):
            return _family_of(name)
    deposit = any(m in ("APY", "dividend rate") for _, _, _, vals, _ in items for m in vals)
    labels = [p.cells[0][1] for p in rows]
    if deposit and all(re.search(r"\b\d+\s*months?\b|certificate", l, re.I) for l in labels):
        return "IRA" if any(_family_of(l) == "IRA" for l in labels) else "Certificate"
    for part in reversed(caption.split(" / ")):
        if _family_of(part):
            return _family_of(part)
    for l in labels:
        if _family_of(l):
            return _family_of(l)
    return _family_of(urlparse(url).path.replace("-", " "))


def _product(name: str, family: str) -> str:
    if not name:
        return family
    if any(w in name.lower() for w in family.lower().replace("&", " ").replace(",", " ").split()[:2]):
        return name
    return f"{family} {name}"


def _measure(h: str) -> str:
    h = h.lower()
    if "yield" in h or "apy" in h:
        return "APY"
    if "dividend" in h:
        return "dividend rate"
    if "annual percentage rate" in h or re.search(r"\bapr\b", h):
        return "APR"
    if re.fullmatch(r"\W*(interest )?rate\W*", h):
        return "rate"
    return ""


def _qual(v: str) -> str:
    v = v.lower().replace("–", "-").replace("—", "-").replace(",", "").replace("$", "")
    v = re.sub(r"\b(months?|mo)\b", "month", v)
    v = re.sub(r"\s*-\s*", "-", v)
    return re.sub(r"\s+", " ", v).strip()


def _value(v: str):
    """'5.39% APR' -> (5.39,); '12.50% – 19.50%' -> (12.5, 19.5); None if the cell holds no rate."""
    nums = re.findall(r"(\d+(?:\.\d+)?)\s*%", v)
    return tuple(float(n) for n in nums) if nums else None


def _differs(a: dict, b: dict) -> bool:
    """Two observations of a fact disagree if any measure both show differs."""
    return any(a[m] != b[m] for m in a.keys() & b.keys())


MEASURE_ORDER = {"APY": 0, "APR": 0, "rate": 1, "dividend rate": 1}


def _show(vals: dict) -> str:
    return " / ".join(f"{' – '.join(f'{x:g}%' for x in v)} {m}"
                      for m, v in sorted(vals.items(), key=lambda kv: (MEASURE_ORDER.get(kv[0], 2), kv[0])))


def _neg(date: str) -> str:
    """Sort key that puts newer ISO dates first."""
    return "".join(chr(0x7F - ord(c)) for c in date)


def build():
    return KnowledgeBase()
