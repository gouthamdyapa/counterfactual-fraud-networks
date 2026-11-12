# Reviewer guide

## Minimum-Cost Temporal Walk Profiles on Depth-Three In-Arborescences

**Author: Goutam Dyapa**  
**Companion prepared: 12 November 2026**  
**Manuscript examined: working version of 5 November 2026, 27 pages**

[Read the manuscript](../manuscript/Goutam_Dyapa_Temporal_Walk_Profiles.pdf) | [Detailed novelty comparison](NOVELTY_COMPARISON.md) | [Download the combined reviewer packet](Goutam_Dyapa_Reviewer_Packet.pdf)

### The question for a reviewer

Does the manuscript prove a new, useful algorithmic guarantee for its precise restricted model, after accounting for temporal reachability, temporal path counting, and generalized deletion propagation?

The candidate contribution is the stated **`2^{O(sqrt(R))} poly(L)` algorithm and polynomial-space bound**, using a sufficient temporal state and partition-bounded configurations. Exact constraints, tree dynamic programming, and min-plus convolution are established ideas. The companion derives a GDP encoding and weighted ILP extension; the formulation and full-table output alone should not carry the novelty claim.

This author-side guide records a focused comparison and evidence map. It does not certify the proofs or originality. The manuscript remains a working paper; its frozen snapshot has not yet incorporated the new GDP analysis.

### Plain-language contribution

Imagine timestamped transfers in a small tree leading to one account. Removing a transfer can break three-transfer chains while also destroying shorter chains that must survive. The algorithm returns the cheapest deletion set for each achievable pair of remaining counts. An upper limit and an exact target can have different answers.

The claim concerns computing this menu when little two-chain loss is allowed. It does not establish an operational transaction intervention, a changed fraud prediction, or reduced fraud.

### Exact scope and notation

| Item | Contract in the manuscript and reference solver |
|---|---|
| Input | An explicit finite event list. The original static graph is a directed in-arborescence toward one root, of depth at most three. Validate it before mandatory deletions. |
| Counts | `W2` and `W3` count strictly time-increasing event tuples ending at the root. Distinct event IDs remain distinct, including parallel events. |
| Choices | Optional event deletions, nonnegative integer costs, and mandatory keep/delete statuses. Mandatory deletion cost is charged once. |
| Baseline | After mandatory deletions, let `N2` and `N3` be the two counts and `T0 = max(T, 0)`. A quota above `N2` is infeasible. |
| Parameter | For a feasible quota, `R = N2 - T0`. The table uses exact loss `ell = N2 - W2` and exact surviving `W3`. |
| Output | Minimum total deletion cost and one attaining set of original event IDs for every attainable exact pair satisfying the quota. |
| Limit | A separate deletion-count cap in a weighted instance is not an additional coordinate of this table. Arbitrary other deletion-sensitive classifier features are outside its guarantee. |

Source: manuscript Section 2 and Theorem 2.1, pp.2-3; [reference solver](../implementation/profile_solver.py).

<!-- pagebreak -->

## Claim-to-evidence map

Page numbers below refer to the named 27-page manuscript, not a different draft. A code correspondence helps inspection; it does not prove a theorem.

| Claim to examine | Manuscript location | Implementation or retained evidence |
|---|---|---|
| Complete minimum-cost exact profiles; subexponential dependence on `sqrt(R)`; polynomial space | Theorem 2.1, p.3; proof in Sections 3-5, pp.4-8 | [`solve_profiles`](../implementation/profile_solver.py); complexity argument must be checked in the proof, not inferred from finite runs |
| Equal-degree final events are interchangeable under every continuation; cheapest canonical choices suffice; deletion charges are disjoint | Lemma 3.1 and Corollary 3.2, p.4 | `_c_groups`, `_c_configurations` in the same solver |
| Branch configuration count is bounded by integer partitions; branches do not multiply this factor | Lemma 3.3, p.5; Section 5, pp.7-8 | `_c_configurations`, `_branch_profile`, `_convolve` |
| Current scalar counts can lose information needed for later decisions | Proposition 3.4, pp.5-6 | [Ten-event illustration](../illustration/instance.json), [expected output](../illustration/expected.json), and [illustration checker](../illustration/check_illustration.py) |
| Chronological state and tie handling are sufficient; completed tables can be combined | Lemma 4.1 and Section 4, pp.6-7 | `_child_profile`, `_convolve`; inspect equal-time event order and shared event identities |
| Unit-cost quota decision is W[1]-hard in deletion budget `b`, and NP-complete | Theorem 6.1, p.8; Appendix A, pp.16-22; Corollary A.7, p.22 | Reduction in the manuscript. This is not a lower bound in preservation loss `R` |
| Count-based predicates can be optimized by a scan; an added dynamic amount feature has a hardness obstruction | Corollary 7.1, p.9; Proposition 7.2, pp.9-10 | `select_profile` implements a predicate/total-cost selection layer; it does not replay a full fraud model |
| Fixed-deletion counting transfers to established forest counting; first-arrival summaries alone lose multiplicity | Proposition B.1 and Appendix B.2, p.23 | Compare [Counting Temporal Paths](https://doi.org/10.1007/s00453-025-01301-3) and the final [reachability article](https://doi.org/10.1016/j.jcss.2024.103549) |
| Finite correctness checks and synthetic transaction findings | Section 10, pp.13-16; Appendix D, pp.24-25 | [Mac correctness summary](../evidence/MAC_VALIDATION_RESULTS.json), [batch export](../results/BATCH_RESULTS.zip), [recomputed totals](../results/recomputed_results.json) |

### Useful reading route

Start with Theorem 2.1 and the normalization in Section 2. Then inspect Lemmas 3.1-3.3 and 4.1, followed by the complexity accounting in Section 5. Read the GDP construction in the [comparison](NOVELTY_COMPARISON.md) before assessing the novelty wording. Appendix A needs a separate reduction check; the experiments cannot validate that hardness proof.

For the worked illustration, distinguish an **exact loss** from a **lower quota**. The saved `global_loss_5` entry fixes `W2 = 5`. A query with `min_w2 = 5` permits larger surviving `W2` and can have a cheaper solution. These are different optimization requests.

<!-- pagebreak -->

## What the experiments support

### Separate correctness suite

The retained [native Mac summary](../evidence/MAC_VALIDATION_RESULTS.json) reports 375 histories, 1,863 threshold calls, 2,529 profile entries, and 54,076 selection queries. The exhaustive validator independently enumerates event tuples and legal deletion subsets rather than calling the solver's optimization helpers. This computational separation supports finite correctness checking; it is not a separate human proof review. See [reproduction and evidence provenance](../docs/REPRODUCIBILITY.md).

### Completed IBM synthetic-data batch

| Outcome | Initial `W3 = 0` | Initial `W3 > 0` | Total |
|---|---:|---:|---:|
| Empty context | 179 | 0 | 179 |
| Unsupported structure | 125 | 155 | 280 |
| Supported, above the 32-event solver cap | 34 | 9 | 43 |
| Fully profiled | 454 | 68 | 522 |
| **All fixed queries** | **792** | **232** | **1,024** |

The positive-case conclusions concern **68 of 232** positive queries. Capped contexts were not proved infeasible. The original context was checked for structural eligibility; conflicting edges were not deleted to create an eligible tree.

For `U = floor(3 * B3 / 4)`, where `B3` is the initial three-event count, and unit optional deletion costs:

| Two-event preservation | Upper bound `W3 <= U`, cost at most 3 | Exact `W3 = U`, cost at most 3 | Exact target unattainable at any cost |
|---|---:|---:|---:|
| 100% | 68 | 13 | 55 |
| 95% | 68 | 14 | 54 |
| 90% | 68 | 15 | 53 |

These are repeated policies on the same 68 positive profiled contexts. The upper-bound target is always feasible without a cost limit by deleting all first-stage events; the observed result concerns the three-deletion limit. Only two queries changed exact attainability or minimum cost as preservation was relaxed.

### Verification and interpretation limits

The native batch reports 935 witness checks. Of 563 completed numeric threshold tables, 528 agreed with exhaustive enumeration: 721 entries and 1,096,402 subset visits. The remaining 35 tables exceeded the 16-optional-event oracle limit; their 214 entries had witness checks without exhaustive optimality checks. No mismatch was reported.

The **89 positive-context tables** have `R` distribution `{0: 68, 1: 18, 2: 3}`. Across **all 563 tables**, the distribution is `{0: 522, 1: 35, 2: 3, 3: 2, 6: 1}`; the larger values occur only with initial `W3 = 0`. These data do not test scaling at large `R`.

The aggregate export lacks complete original contexts and native deletion witnesses. Reaggregation checks record consistency and totals, not a fresh replay. The cohort had already been studied, may contain overlapping contexts, and is not a held-out evaluation. Its 18,432 policy rows are not independent experiments. No fraud-accuracy or operational-effectiveness improvement is measured.

Sources: [results guide](../docs/RESULTS.md), [aggregate export](../results/BATCH_RESULTS.zip), [recomputed JSON](../results/recomputed_results.json), and [frozen protocol](../batch/batch_protocol.json). The later [interactive explorer](../explorer/README.md) has separate fixture checks; they do not enlarge the manuscript's experimental sample.

<!-- pagebreak -->

## Questions that would make a review actionable

1. **Correctness.** Is the final-event equivalence valid under every continuation, with equal timestamps, parallel IDs, forced choices, and nonnegative binary costs? If not, give the smallest counterexample and the failed lemma.
2. **Running time and space.** Does the charging argument bound every enumerated branch configuration by preservation loss, and does the processing order avoid multiplying partition factors across branches? Are witness recovery, integer arithmetic, and all retained tables polynomial in explicit input length?
3. **Prior-art implication.** Does a specific existing theorem imply Theorem 2.1 after a transformation? Please identify the theorem, give the encoding, and bound both its size and controlling parameter. GDP expressibility alone does not supply that complexity analysis.
4. **Alternative state or algorithm.** Can known query, ordered-incidence, or temporal-graph methods recover the result with the same or better guarantee? The direct first-arrival counterexample does not exclude richer constructions.
5. **Hardness.** Does Appendix A preserve graph depth, optional unit-cost events, both quotas, and the deletion budget in both directions? The manuscript uses `b` for deletion budget and `R` for preservation loss.
6. **Evidence and relevance.** Is the synthetic batch a useful illustration of exact-target gaps given its eligibility rate and small parameter range? What additional weighted instances, controlled `R` scaling, or generic ILP baseline would materially test practical value?
7. **Publication positioning.** If the proof is correct, is the specialized parameterized result sufficiently distinct and substantial for the intended venue? Which precise claim needs narrowing or which closest source is still missing?

A useful response can be short: **claim assessed; verdict; theorem/page or counterexample; required revision**. No reviewer is being asked to endorse originality without checking the relevant result.

### Reproduce the lightweight checks on a Mac

From the repository root, with Python 3.8 or newer:

```bash
cd temporal-profiles
python3 verify_artifacts.py
python3 implementation/demo.py
python3 analysis/summarize_batch.py results/BATCH_RESULTS.zip
```

These commands check integrity, run the bundled examples, and summarize saved results. They need no IBM dataset and do not rerun the original Mac batch. The [full reproduction guide](../docs/REPRODUCIBILITY.md) documents the optional exhaustive suite and dataset run.

### Version and provenance

The comparison uses repository base commit `cc03ddb6454f00378fae2f5570144f741090fe87`. The scientific snapshot remains unchanged; the companion is outside its frozen checksum manifest.

| Artifact | SHA-256 |
|---|---|
| Named manuscript PDF | `13bd3266bb3a045d5acf6e45b95667f18f69fa8ee2b44451abd1377630021941` |
| Reference solver | `a9f8f2c9f276055ab570940d784244192d177c16299f7a295ad75c481de7f4ba` |
| Native batch export | `cd16912a10fe1f1e8444824f5a0648b57f2c2b05133e50be5bb1f24d522204c2` |

Goutam Dyapa ran the reported macOS experiments. ChatGPT assisted with manuscript drafting and revision, code development, and validation tasks, as disclosed in the manuscript. ChatGPT also assisted in preparing this review companion. This disclosure does not imply independent human review.

