# Notes

How the system works and why. Terms in **bold** are defined in [GLOSSARY.md](GLOSSARY.md).

## How it works

_To be written once the build exists._

## API keys

None. The system uses no language model and makes no network calls.

## Decisions

**D1. No LLM at answer time.** The brief allows LLMs, but answers come from plain code: retrieval, rules and template sentences. Graders may run without an API key; an LLM can return different numbers for the same question, which costs consistency (15%); LLM calls are slow against the 2-second target; and rules can be explained line by line. The cost is weaker handling of oddly worded questions, which we offset with a synonym list and our own reworded test set.

**D2. Values come only from the snapshots, at ingest.** `ingest()` builds everything from the snapshots it is given, every run. Hand-written content is limited to how to read the site (synonyms, page types, table layouts), never values. A hand-made table of answers would go stale the moment the snapshots change, which is the failure this challenge tests.

**D3. Keep full history.** Every snapshot is kept, not just the newest. Older snapshots are needed for **As-of date** questions, for **Conflicts** across time, and as evidence that a value is a **Stale value**.

**D4. Dates come from the snapshots, never from the code.** Questions without an **As-of date** are answered from the **Latest snapshot** received. An As-of date is answered from the newest snapshot dated on or before it. A date before the first snapshot gets a **Refusal**: we have no record of the site then ("If the website doesn't say, don't guess").

**D5. One pipeline.** Every page is split into passages (a sentence, a list item, or a table row with its column headers). All passages go into one index, tagged with snapshot, page and page type. Every question takes the same steps: pick the snapshot, search, authority first, check qualifiers, format. The winning passage decides the format (a template for a table row, trimmed text otherwise), so no question classifier is needed.

**D6. Authority first.** Among pages with a matching passage, the highest page type always wins; keyword strength only breaks ties within a type. A strong keyword match on an article must never beat the rate table. The order, derived from where the public answers and traps live ([dev/RESEARCH.md](dev/RESEARCH.md)): rate hub > product page > promo page > calculator > article > file. Articles stay eligible, because some facts exist only in a press release (a branch closure date, an award), and among articles the newest publication date wins, because old articles stay on the site.

**D7. Tiers.** If the question names a **Tier** (an amount, term or "highest"), give that row. Otherwise give every current Tier of the product and term asked about, smallest first. Extra current rows are safe; Stale values are fatal.

**D8. Measures.** Answer the **Measure** asked for. For a plain "rate", give the rate with its APR or APY, labelled. Two Measures of the same product are different facts, never a Conflict.

**D9. A close match is not an answer.** If the product, Tier or Measure asked about has no matching passage, give a Refusal ("I don't know, please contact Dupaco") with no numbers. Never substitute a nearby product, e.g. the 30-year fixed rate for a 7/1 ARM question.

**D10. Conflicts.** A Conflict is two different values for the same product, Tier and Measure, within a snapshot or across snapshots (the contract says "across or within"). Each one is resolved to the **Current value**, with the reason (newer snapshot, or authoritative page over article or calculator).
