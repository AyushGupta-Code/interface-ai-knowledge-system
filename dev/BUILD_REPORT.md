# Measured Build Report

All seven requested code steps were retained and committed separately. All five checks ran after every step; detailed commands and rejected variants are in PLAN.md. Reports containing supplied text remain only in ignored results/build/. No organizer files changed and nothing was pushed.

| Step | Status | Public | Reworded | Must-refuse | Practice | Conflict F1 | Commit |
|---|---|---:|---:|---:|---:|---:|---|
| Q1 | Kept | 0.7736 | 0.7300 | 17/18 | 0.8300 | 0.7586 | `b31ee8b` |
| Q2 | Kept | 0.7736 | 0.7300 | 17/18 | 1.0000 | 0.7586 | `5f751bc` |
| Q3 | Kept | 0.7736 | 0.7300 | 17/18 | 1.0000 | 0.7586 | `9db570d` |
| Q4a | Kept | 0.7736 | 0.7300 | 17/18 | 1.0000 | 0.7586 | `40ec396` |
| Q4b | Kept | 0.7969 | 0.7528 | 17/18 | 1.0000 | 0.7586 | `fe88773` |
| Q4c | Kept | 0.8512 | 0.7943 | 17/18 | 1.0000 | 0.7586 | `952e65c` |
| Determinism | Kept | 0.8512 | 0.7943 | 17/18 | 1.0000 | 0.7586 | `a54a3b4` |

Conflict negatives remained0/8 failing and resolution accuracy1.0 throughout. All original sets have zero stale traps/errors. Must-refuse is reported as item count: concurrent runs sometimes reduced its speed-weighted aggregate; a serial empty-environment run confirms final0.9444 and p951.70s.

## Changed item scores

- **Q1:** practice: t1 0 → 1; practice: t2 0 → 1; practice: t1b 0 → 1
- **Q2:** practice: t3 0 → 1
- **Q3:** No item-score changes.
- **Q4a:** No item-score changes.
- **Q4b:** public: dup-008 0 → 1; reworded: dup-008-p1 0 → 1; reworded: dup-008-p2 0 → 1
- **Q4c:** public: dup-073 0 → 1; public: dup-087 0 → 1; reworded: dup-073-p2 0 → 1; reworded: dup-087-p1 0 → 1; reworded: dup-087-p2 0 → 1
- **Determinism:** No item-score changes.

Q1 also changes reworded aggregate consistency without changing any Dupaco item correctness. The title-only Q4a mechanism adds supported capability but does not improve these measured item scores.

## Rejected or superseded attempts

| Attempt | Public | Reworded | Refuse | Practice | F1 | Why not final |
|---|---:|---:|---:|---:|---:|---|
| `q1` | 0.7736 | 0.7171 | 17/18 | 0.8300 | 0.7586 | Unitless spelled-year qualifiers reject equivalent month terms; replaced with typed terms. |
| `q2` | 0.7736 | 0.7284 | 17/18 | 1.0000 | 0.7586 | Normal-answer date display reduces paraphrase consistency; restored existing display. |
| `q2_final` | 0.7736 | 0.7300 | 17/18 | 1.0000 | 0.7586 | Different-URL withdrawal missing from guard; strengthened before retention. |
| `q2_safe` | 0.7736 | 0.7300 | 17/18 | 1.0000 | 0.7586 | Superseded by broader expiry/withdrawal guards. |
| `q2_expiry` | 0.7736 | 0.7300 | 17/18 | 1.0000 | 0.7586 | Superseded by family-level withdrawal checks. |
| `q2_kept` | 0.7736 | 0.7300 | 17/18 | 1.0000 | 0.7586 | Superseded by absent-current conflict resolution guard. |
| `q4b` | 0.7969 | 0.7528 | 17/18 | 1.0000 | 0.7586 | Unsupported feature/modifier could bypass rate guards in link path. |
| `q4b_safe` | 0.7969 | 0.7528 | 17/18 | 1.0000 | 0.7586 | Added structural personal/business scope before retention. |

## Finishing gates

| Gate | Result |
|---|---|
| Public ≥0.85 | Pass:0.8512 |
| Final-score public/reworded gap ≤0.05 | **Fail:0.0569** |
| Organizer practice | Pass:5/5, conflict F1/resolution1.0 |
| Synthetic fallback/date/cache/provenance and parser checks | Pass:36/36 |
| Cross-process seeds0,1,42 | Pass:37/37; complete answer/source/conflict hashes identical |
| Full October snapshot direct checks | Pass:40/40, includes current value and preserved historical answer |
| Strict October harness scoring | **Fail:40/41 checks; score0.575,1stale trap,0errors** |
| Fresh local checkout, no site packages/API keys | Pass under available Python3.14.4: practice1.0,public0.8512,p950.23s |
| Cold Python3.11 runtime | **Unverified:interpreter unavailable**;3.11 syntax parse passes |

The strict October mutation changes one personal12-month certificate APY to synthetic4.44%. An unchanged business3.40% is a different valid scope, but the answer also retains stale personal3.40% from product pages alongside authoritative personal4.44%. This demonstrates a real same-fact authority failure in family-list assembly. The original synthetic question/trap is retained; the branch-scope ambiguity is documented rather than used to dismiss the genuine stale-copy bug. Historical item scores1.0; current item0.15.

This contradicts the intended authority guarantee for family lists. No further retrieval tuning was performed after the agreed bounded round. The remaining unsupported J.D.Power award case, lexical prose limitations, unmet score-gap gate and unavailable3.11 runtime are documented in NOTES.md and PLAN.md. The system-design figure is unchanged. No untouched question set was created or used.
