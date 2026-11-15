"""Build dev/shape_eval.jsonl: typos, answer-type wording, lists of terms and counts of unpublished things.

Written after the second sealed set's diagnosis named these patterns (fixes 4-6), from public topics and
values read off the latest snapshot's /rates table and public answer keys; not from any sealed set. It is a
development set (tuned against), not a holdout. Usage: python3 dev/make_shape_eval.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def item(i, q, cat, must, must_not=(), as_of=None):
    return {"id": f"shape-{i:02d}", "question": q, "as_of": as_of, "expected_answer": "", "must_include": list(must),
            "must_not_include": list(must_not), "category": cat, "difficulty": "medium", "weight": 1.0,
            "expected_sources": [], "group": None}


ITEMS = [
    # 4. answer type and spelling
    item(1, "what's the closing time for the lobby on saturday", "branch_info", ["12:30"]),
    item(2, "60 month auto loan 2025 apr, not sure which page to trust", "stale_trap", ["5.39%"], ["5.34%"]),
    item(3, "whats the curent mortage rate", "tier_disambiguation", ["7.13"], ["6.7%", "6.037%"]),
    item(4, "platnum visa purchase apr", "tier_disambiguation", ["12.5"], ["9.9%"]),
    item(5, "dupaco routng number", "entity_attribution", ["273974581"]),
    item(6, "hometart grant how much can i get", "current_value", ["15,000"]),
    item(7, "regular 12mo cd apy pls", "tier_disambiguation", ["3.40%"]),
    item(8, "When does the drive-up open on weekdays? Need the opening time.", "branch_info", ["8 a.m."]),
    # 5. lists of a family's terms
    item(9, "What terms can I choose for a personal loan?", "list_completeness", ["9.99%", "10.49%", "10.99%", "12.49%"]),
    item(10, "List every regular certificate term you offer.", "list_completeness", ["1.80%", "3.40%"]),
    item(11, "Which auto loan terms can I choose for a 2025 car?", "list_completeness", ["5.19%", "5.39%", "5.49%", "5.59%"]),
    # 6. counts: a number of the counted thing, or a refusal
    item(12, "How many ATMs does the Galena branch have?", "should_refuse", []),
    item(13, "How many drive-up lanes does the Peosta branch have?", "should_refuse", []),
    item(14, "How many tellers work at the Galena office?", "should_refuse", []),
    item(15, "How many branch offices does Dupaco have?", "conflict_resolution", ["22"], ["24 branch"]),
]


def main():
    (ROOT / "dev/shape_eval.jsonl").write_text("".join(json.dumps(o) + "\n" for o in ITEMS))
    print(len(ITEMS), "questions")


if __name__ == "__main__":
    main()
