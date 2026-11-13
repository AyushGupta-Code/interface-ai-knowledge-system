# Research findings

Where each public answer and each Forbidden value lives, and what that means for the build. Terms are defined in [GLOSSARY.md](../GLOSSARY.md).

How it was produced: `python3 dev/research_map.py > <scratch>/map.txt` (about 3 min). For each question it lists the pages in the target Snapshot holding each required value, and every page in every Snapshot holding each Forbidden value, using the scorer's own `contains()` rule. The output quotes site text, so it stays out of git.

## 1. Where the traps are

Each public Forbidden value falls into one of these groups:

| Trap | Examples | Where it lives |
|---|---|---|
| **Another product on the same rate page** | dup-045/046 Share Savings: 0.30 / 0.35 / 0.40% | Current rows of *Investor's Choice Money Market* and *Health Savings Account*, on `/rates` and `/personal/savings-account`, in every Snapshot. Share Savings itself has been 0.15 / 0.20% since May. |
| **Wrong product altogether** | dup-101 student loan: "Share Savings", 0.20% | Savings tables |
| **A stale page that is still live** | dup-009/011 mortgage: 6.037 / 6.061 / 5.954% | `/homebuying-guidance`, unchanged in all 5 Snapshots |
| **A calculator or promo page that was never updated** | dup-016/017 auto: 5.34%, 5.54% | `/calculators/vehicle-affordability` and `/switch-and-earn` (a promo page that also shows current personal-loan rates, so it is *partly* stale) |
| **An older article** | dup-073 "24 branch"; dup-087 Forbes "fourth" | Older newsroom articles; a newer one says 22 branches / "fifth time" |
| **An expired promotion** | dup-052 "3% APY" | `/checking-offer-lp` and older articles |
| **The value from a different Snapshot** | dup-006 as of May: 4.00% | The 10-month jumbo special became 4.00% only in Snapshot 05 |
| **Not on the site at all** | 6.7%, 9.9%, info.dupaco.com URLs, "unable to find", "in these facts" | Catch invented numbers and sloppy generated text |

**This corrects an earlier assumption.** Forbidden values *are* sometimes current values, but always of a **different product** on the same page, never another Tier of the product asked about. So D7 holds (all Tiers of the asked product are safe), and the qualifier check must match the **product name of the row**, not just the page.

## 2. Page-type ranking (D6)

URL → page type is reliable for this site (705 pages in Snapshot 05: ~255 `/learn`, ~167 `/newsroom`, ~117 `/business/resources`, 30 `/calculators`, ~30 product and rate pages).

Evidence-based order:

1. **Rate hub**: `/rates`, `/business-rates`
2. **Product page**: `/personal/...`, `/business/...` (not resources), `/checking`, `/about/join`, `/contact`
3. **Promo / landing page**: `*-lp`, `/switch-and-earn`, `/earn-more`, offer pages
4. **Calculator**: `/calculators/...`
5. **Article / press / guidance**: `/learn`, `/newsroom`, `/business/resources`, `/resources`, dated `/20xx/` paths, `/homebuying-guidance`
6. **File**: `/hubfs/...` PDFs and spreadsheets

Two refinements the data forces:

- **Articles must stay eligible.** Several answers exist *only* in a newsroom article: the Hy-Vee branch closure date (dup-074/075), Volunteer Time Off count (dup-088), Home$tart grant (dup-031), Forbes recognition (dup-087). Authority first means "rank articles last", not "exclude them".
- **Among articles, the newest publication date wins.** "22 branches" vs "24 branches" and Forbes "fifth" vs "fourth" are both settled by article date, not Snapshot date: the old articles are still present in Snapshot 05. The article's own date has to be extracted at ingest.

## 3. Rate tables are copied across many pages

The same rate table appears on the rate hub, several product pages, a promo page and even an article (`/learn/master-your-money/homeownership/` carries the full mortgage table). So many pages "contain the answer". The ranking decides which one to cite, and Conflicts must not be raised between identical copies.

## 4. What changed over time (As-of questions and Conflicts)

Tracking every percentage row on 5 rate pages across Snapshots:

- **Mortgage rates changed in every Snapshot.** 30-year ≤ $100k: 5.875% → 6.250% → 6.125% → 6.375% → 7.13%. The table format also changed in Snapshot 05 (three decimals and a Points column before, two decimals after).
- **12-month certificate**: 2.90% → 3.40% APY in Snapshot 03.
- **10-month specials**: jumbo 3.90% → 4.00%, regular 3.80% → 3.90% APY in Snapshot 05.
- Most other rows did not change.

**Parser hazard:** footnote markers are glued onto values (`4.10%2`, `0.20%1`). A naive diff reports 108 of 188 rows as "changed" when most only gained a footnote digit. Strip trailing footnote digits after `%` before comparing or quoting.

## 5. Refusal questions

- **7/1 ARM rate (dup-145):** the site has an article about adjustable-rate mortgages but no ARM rate row anywhere. Refuse.
- **Construction-loan rate (dup-147):** business construction-loan pages exist, without a rate. Refuse.
- **Mullan Avenue branch hours (dup-102):** "Mullan" only appears in member stories in blog posts; there is no such branch on `/contact`. Refuse.

All three confirm D9: a matching topic is not a matching row.

## 6. Non-rate answers

- **Branch addresses and the routing number** are on `/contact`.
- **Lobby and drive-up hours** appear only in newsroom articles about specific branches, and they differ by branch (Saturday 8:30–12:30 at some, 9–noon at others). dup-104 ("Do all branches keep the same hours?") expects the answer to show the variation.
- **Mobile wallets** are on `/online-and-mobile-banking/mobile-payments` and `/brighttrack` (classified "other" today; should map to product/help).

## 7. Answer-key quirks

- **dup-005** ("Get me the rate for the certificate of accounts") has an empty `must_include`, so it scores 0 for every system unless the optional LLM judge runs. Not worth optimising for.
- **dup-011's prose** says "15-year 6.25%"; the site says 6.75%. The scorer only uses the lists.

## 8. Article publication dates

530 of 538 article pages in Snapshot 05 (`/learn`, `/newsroom`, `/business/resources`) carry the date on a line of its own near the top (`Mar 22, 2023`). The other 8 have it in the byline (`Written by … | Apr 16, 2025 11:37:36 AM`). Those two patterns cover every article.

## 9. Synonyms

Gathered while writing the reworded test set ([make_paraphrase_eval.py](make_paraphrase_eval.py), 80 items, 2 per public question). Each group maps to the site's own wording, which comes first:

| Site term | Member wording |
|---|---|
| mortgage | home loan, house loan |
| certificate | CD, certificate of deposit, share certificate |
| auto loan | car loan, vehicle loan |
| 30-year | thirty-year, 30 yr, 30-yr (same for other terms: "three-year" = 36 months) |
| month | mo, months |
| drive-up | drive-through, drive-thru, drive up window |
| lobby hours | branch hours, opening hours, when open |
| routing number | ABA, routing transit number |
| credit card | Visa, card |
| APY | yield, earn, interest (on deposits) |
| APR | interest rate (on loans) |
| join / become a member | membership, sign up, apply |
| mobile wallet | Apple Pay, Google Pay, Samsung Pay, tap to pay |
| adjustable-rate mortgage | ARM, 7/1, 5/1 |
| student loan | college loan, university loan |
| contact information | address, phone number, contact details |

Baseline on the reworded set: the starter scores **0.127** (public set: 0.093).
