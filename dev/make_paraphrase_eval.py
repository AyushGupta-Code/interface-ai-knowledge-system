"""Build dev/paraphrase_eval.jsonl: our own rewordings of the public questions (Q7 / Gates).

Each rewording reuses the public item's Answer key (must / must-not lists, category, weight, sources)
and keeps the public id as its `group`, so the scorer's consistency check compares it with the original.
Rewordings only change the wording, never the fact asked for. The wording deliberately uses synonyms
and casual phrasing the public set doesn't, to catch keyword overfitting.

Usage: python3 dev/make_paraphrase_eval.py   (writes dev/paraphrase_eval.jsonl)
Score: python3 harness/run_eval.py --submission submission --eval dev/paraphrase_eval.jsonl
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# public id -> rewordings (optionally (question, as_of) to override the date)
REWORDINGS = {
    "dup-001": ["What APY does the 17 month certificate special pay?", "how much does the 17-month CD special earn"],
    "dup-009": ["What's the current rate on a thirty-year fixed home loan?", "30 yr mortgage interest rate?"],
    "dup-011": ["What are your home loan rates today?", "Current mortgage interest rates please"],
    "dup-016": ["APR on a 60 month car loan for a 2025 vehicle?", "If I finance a 2025 model year car for 60 months, what's the APR?"],
    "dup-034": ["Which credit cards does Dupaco have, and what APR does each one charge?", "list your Visa cards and their interest rates"],
    "dup-045": ["What's the dividend rate on a Share Savings account holding $15,000?", "Share Savings rate for balances from $10,000 to $24,999.99?"],
    "dup-054": ["What's the routing number for Dupaco?", "Dupaco ABA routing number"],
    "dup-064": ["When are Dupaco branch lobbies open?", "What time do your lobbies open and close?"],
    "dup-066": ["When is the drive-through open?", "drive up window hours?"],
    "dup-068": ["Where is the Galena branch located?", "Galena IL branch address"],
    "dup-073": ["How many branch locations does Dupaco operate?", "number of Dupaco branches?"],
    "dup-075": ["Can I still visit the Hy-Vee branch this October?", "Is the Dupaco branch inside Hy-Vee open now?"],
    "dup-087": ["Has Forbes ranked Dupaco? How many times?", "What Forbes awards has Dupaco won?"],
    "dup-008": ["Where on the website can I find certificate rates?", "Which page lists your share certificate rates?"],
    "dup-052": ["What interest do your checking accounts pay?", "checking account APY?"],
    "dup-035": ["What's the regular purchase APR on the Platinum Visa card?", "Platinum Visa purchase rate?"],
    "dup-145": ["Do you offer a 7/1 ARM, and what's the rate?", "rate for a 7-1 adjustable mortgage?"],
    "dup-065": ["What hours are your branches open?", "When can I visit a branch lobby?"],
    "dup-074": ["What date is the Hy-Vee branch closing?", "When will the Hy-Vee location shut down?"],
    "dup-050": ["What APY does Bright Savings pay?", "How much interest does the Bright Savings account earn?"],
    "dup-040": ["What are the APRs on your credit cards?", "credit card interest rates?"],
    "dup-080": ["Where can I find a branch or ATM near me online?", "link to the Dupaco location finder"],
    "dup-049": ["Is there a savings tier that earns 0.35% APY?", "Can I get 0.35% APY on a Dupaco savings account?"],
    "dup-031": ["Tell me about the Home$tart grant", "What does Dupaco's Home$tart homebuyer program offer?"],
    "dup-028": ["APR for a personal loan over 36 months?", "What rate would I pay on a three-year personal loan?"],
    "dup-147": ["What's the rate on a construction loan?", "How much interest for a home construction loan?"],
    "dup-076": ["The Hy-Vee branch is closing; which branches offer full service instead?", "Where should Hy-Vee branch members bank now?"],
    "dup-006": [("What APY did the 10 month fixed jumbo certificate special pay in May 2026?", "2026-05-31"),
                ("10-month jumbo certificate special rate as of mid-May 2026?", "2026-05-15")],
    "dup-055": ["Tell me the routing number again", "What routing number do I use for Dupaco?"],
    "dup-005": ["What are your certificate rates?", "rates on certificates of deposit?"],
    "dup-017": ["What's the APR on an 84 month loan for a 2024 car?", "84-month auto loan APR, 2024 model year?"],
    "dup-081": ["Who can join Dupaco?", "Am I eligible for Dupaco membership?"],
    "dup-060": ["How do I change my address or phone number with Dupaco?", "I need to update my contact details. How?"],
    "dup-046": ["What's the top APY on Share Savings?", "Highest rate a Share Savings account can earn?"],
    "dup-102": ["What are the Mullan Avenue branch hours?", "When is the Mullan Ave. location open?"],
    "dup-104": ["Are lobby hours the same at every branch?", "Do branch hours differ by location?"],
    "dup-088": ["How many employees took Volunteer Time Off last year?", "How many Dupaco staff used VTO?"],
    "dup-101": ["Do you have loans for college students?", "I'm starting university; what flexible loans do you offer students?"],
    "dup-094": ["Does Dupaco work with Apple Pay or Google Pay?", "Can I use my Dupaco card in a mobile wallet?"],
    "dup-082": ["How can I become a member online?", "Where do I apply for Dupaco membership online?"],
}


def main():
    public = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "eval/public_eval.jsonl").read_text().splitlines()}
    missing = set(public) - set(REWORDINGS)
    assert not missing, f"no rewordings for {sorted(missing)}"
    out = []
    for pid, variants in REWORDINGS.items():
        for i, v in enumerate(variants, 1):
            q, as_of = v if isinstance(v, tuple) else (v, public[pid]["as_of"])
            item = dict(public[pid], id=f"{pid}-p{i}", question=q, as_of=as_of, group=pid)
            out.append(json.dumps(item))
    (ROOT / "dev/paraphrase_eval.jsonl").write_text("\n".join(out) + "\n")
    print(f"wrote {len(out)} items for {len(REWORDINGS)} public questions")


if __name__ == "__main__":
    main()
