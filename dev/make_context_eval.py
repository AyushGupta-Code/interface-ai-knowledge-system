"""Build dev/context_eval.jsonl: public facts asked the way members split them over two sentences, or with a
product ruled out ("not the jumbo one").

Each item reuses a public item's answer keys (category, must_include, must_not_include, sources) with a
hand-written question: the subject in one sentence and "its"/"that" in the asked one, or a negation. Written
from the public set only, after the second sealed set's diagnosis named the two patterns; it is a
development set (tuned against), not a holdout. Usage: python3 dev/make_context_eval.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = [
    ("dup-001", "ctx1", "I'm looking at your 17-month special certificate. What APY does it pay?"),
    ("dup-009", "ctx1", "We're shopping for a 30-year mortgage. What interest rate are you quoting for that?"),
    ("dup-016", "ctx1", "I'm financing a 2025 model-year vehicle over 60 months. What APR would that get?"),
    ("dup-035", "ctx1", "I carry the Dupaco Platinum Visa. What's the standard purchase APR on it?"),
    ("dup-045", "ctx1", "My Share Savings balance is between $10,000 and $24,999. What dividend rate does that earn?"),
    ("dup-028", "ctx1", "I'm considering a personal loan paid back over 36 months. What's the APR for that term?"),
    ("dup-050", "ctx1", "A friend told me about the Bright Savings account. What rate does it pay?"),
    ("dup-054", "ctx1", "My employer is setting up direct deposit to Dupaco. Which routing number should they use?"),
    ("dup-094", "ctx1", "I have Dupaco debit and credit cards. Which mobile wallets can I add them to?"),
    ("dup-017", "ctx1", "My car is a 2024 model and I want to pay it off over 84 months. What APR applies?"),
    ("dup-001", "neg1", "What APY does the 17-month special certificate pay, not the jumbo one?"),
    ("dup-001", "neg2", "For the non-jumbo 17-month certificate special, what's the APY?"),
    ("dup-035", "neg1", "What's the standard purchase APR on the Platinum Visa rather than the Rewards Visa?"),
    ("dup-046", "neg1", "Not the money market, just Share Savings: what's the highest APY?"),
    ("dup-045", "neg1", "What dividend rate does Share Savings earn between $10,000 and $24,999, instead of the money market?"),
]


def main():
    items = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "eval/public_eval.jsonl").read_text().splitlines() if l.strip()}
    out = [dict(items[src], id=f"{src}-{tag}", question=q, group=None) for src, tag, q in QUESTIONS]
    (ROOT / "dev/context_eval.jsonl").write_text("".join(json.dumps(o) + "\n" for o in out))
    print(len(out), "questions")


if __name__ == "__main__":
    main()
