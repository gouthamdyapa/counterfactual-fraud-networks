# Completed Mac batch results

The source record is [BATCH_RESULTS.zip](../results/BATCH_RESULTS.zip), run
`batch_20261106T042058Z_93e46c5d`. The export contains `BATCH_SUMMARY.json`,
`CASE_RESULTS.jsonl`, `GOAL_RESULTS.jsonl`, `PROTOCOL.json`, and `RESULTS.txt`.
The recorded status is `completed_with_limits`: all 1,024 queries have outcomes,
and none is pending. It does not mean every context was supported or profiled.

## Coverage

| Disposition | Initial W3 = 0 | Initial W3 > 0 | Total |
|---|---:|---:|---:|
| Empty context | 179 | 0 | 179 |
| Unsupported structure | 125 | 155 | 280 |
| Supported, above the 32-event solver cap | 34 | 9 | 43 |
| Fully profiled | 454 | 68 | 522 |
| **Total** | **792** | **232** | **1,024** |

The 68 positive fully profiled queries are 29.3% of the 232 positive queries.
The 43 capped contexts were not proved infeasible. No solver or exhaustive-check
timeout was recorded in this completed run.

## Exact targets versus upper bounds

For each original pair of counts `(B2, B3)`, the preservation threshold is
`T = ceil(p * B2 / 100)` and the three-event target is `U = floor(3 * B3 / 4)`.
Each optional deletion has unit cost. The following table uses the same 68 positive
fully profiled queries at every preservation policy.

| Two-event preservation | W3 <= U attainable with cost <= 3 | W3 = U attainable with cost <= 3 | W3 = U unattainable at any cost |
|---|---:|---:|---:|
| 100% | 68 | 13 | 55 |
| 95% | 68 | 14 | 54 |
| 90% | 68 | 15 | 53 |

For the upper-bound goals, 59 queries required one deletion, eight required two,
and one required three. The full-preservation upper-bound goal is always feasible
without a cost limit by deleting all first-stage events; the empirical observation
here concerns feasibility within the three-deletion limit.

Only `q0204` and `q0208` changed minimum cost or exact attainability as preservation
was relaxed. Rounding gave the same numeric threshold for all three policies in
50 of the 68 positive contexts. The 89 distinct positive-context threshold tables
had preservation loss R equal to 0, 1, or 2. This is not a large-R scalability study.

## Verification

The native run reported 935 profile witnesses checked. Of 563 completed numeric
threshold tables, 528 agreed with exhaustive enumeration, covering 721 profile
entries and 1,096,402 subset visits. Visits can repeat subsets across thresholds.
The remaining 35 tables exceeded the 16-optional-event exhaustive-check limit;
their 214 entries had witness checks but no exhaustive optimality check.
No mismatch was reported.

For the 55 full-preservation exact-target gaps, 47 were exhaustively checked and
eight were outside the exhaustive size limit. Excluding the previously inspected
pilot leaves 54 such gaps in 67 other positive contexts.

The aggregate export does not contain the complete original contexts, profiles,
or deleted event IDs. Reaggregating it checks record consistency and reported
totals; it does not independently replay the native witnesses. Full diagnostic
files remain with the original Mac run.

## Interpretation

The cohort was selected in an earlier audit without labels or structural/solver
outcomes. It had already been studied and is not held-out evaluation. Queries may
share accounts and events. The 18,432 policy rows are repeated questions over the
1,024 contexts, not independent experiments. The 8,172 already-satisfied rows arise
from the 454 profiled contexts whose initial W3 is zero.

The data are synthetic IBM AML transactions. No change in fraud accuracy, financial
loss, real-world laundering, or operational deployment is demonstrated. The model
requires an original directed in-arborescence of depth at most three; the batch did
not remove conflicting edges to manufacture supported inputs.

Sources: the unchanged [aggregate export](../results/BATCH_RESULTS.zip),
[recomputed totals](../results/recomputed_results.json),
[frozen protocol](../batch/batch_protocol.json), and Section 10.3 of the
[manuscript](../manuscript/Goutam_Dyapa_Temporal_Walk_Profiles.pdf).
