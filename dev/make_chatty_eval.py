"""Build dev/chatty_eval.jsonl: every public question with conversational padding added mechanically.

The answer keys are the public ones; only the wording changes. Each wrapper adds words a member might say
that are not the subject of the question ("planning", "honestly", "figure out"...). This measures whether
filler words make the system refuse or pick the wrong page. It is a development set (tuned against), not
a holdout. Usage: python3 dev/make_chatty_eval.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPERS = [
    ("Quick question before I head out today: ", ""),
    ("My spouse and I were chatting about this over dinner. ", " Thanks so much!"),
    ("Sorry if this is obvious, but ", " I couldn't figure it out myself."),
    ("I'm trying to plan ahead for next month. ", ""),
    ("", " Honestly just want a straight answer."),
    ("Hey there! ", " Appreciate the help."),
]


def lowered(q):
    return q[0].lower() + q[1:] if q[:2] != q[:2].upper() else q


def main():
    items = [json.loads(l) for l in (ROOT / "eval/public_eval.jsonl").read_text().splitlines() if l.strip()]
    out = []
    for n, it in enumerate(items):
        for k in range(2):
            pre, post = WRAPPERS[(2 * n + k) % len(WRAPPERS)]
            q = it["question"]
            q = (pre + (lowered(q) if pre.endswith("but ") else q) + post).strip()
            new = dict(it, id=f"{it['id']}-c{k + 1}", question=q, group=f"{it['id']}-chatty")
            out.append(new)
    (ROOT / "dev/chatty_eval.jsonl").write_text("".join(json.dumps(o) + "\n" for o in out))
    print(len(out), "questions")


if __name__ == "__main__":
    main()
