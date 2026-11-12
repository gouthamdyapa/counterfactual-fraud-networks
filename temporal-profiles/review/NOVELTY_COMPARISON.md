# Novelty comparison

**Goutam Dyapa | 12 November 2026**  
Companion to the 5 November 2026 working manuscript. [Reviewer guide](REVIEWER_GUIDE.md) | [Combined PDF](Goutam_Dyapa_Reviewer_Packet.pdf)

## 1. Assessment and closest results

**The defensible candidate is a specialized algorithmic theorem.** The problem can be connected to a broad existing deletion-propagation framework. Computing a full exact profile, using strict temporal paths, or using a tree dynamic program is insufficient by itself to establish originality. The review should test the particular sufficient state, preservation-loss charging, configuration bound, and resulting time and space guarantees.

This is a focused comparison with four primary research sources, not an exhaustive novelty search. It neither proves that Theorem 2.1 is new nor establishes that an existing theorem implies it. The derived construction below makes the formulation overlap concrete.

| Prior work and exact location | Established overlap | What still needs an argument |
|---|---|---|
| Makhija and Gatterbauer, GDP [1], Definition 4.1, p.2670; Section 5, pp.2672-2676 | Multiple views can have simultaneous deletion and preservation requirements; a general ILP handles their shared source decisions. Self-joins and set/bag semantics are supported. | Whether a theorem for the encoded joint problem yields the manuscript's preservation-loss bound. Binary event costs are an explicit ILP extension here, not a claim about the literal cardinality objective in Definition 4.1. |
| Molter, Renken and Zschoche [2], Theorems 14-15, pp.10-12 | Polynomial forest reachability optimization; strict traversal is included. The weighted delay model has reached-vertex weights and protected contacts. Its DP uses first-arrival information and min-plus budget combination. | A transfer must preserve exact tuple multiplicities, shared event decisions, costs and the relevant parameter. Reached-vertex weights do not directly equal deletion costs. |
| Enright, Meeks and Molter [3], Theorem 2, p.754 | Temporal path counting on forests with `n` vertices takes `O(n * lifetime^2)` time. The manuscript's Proposition B.1 gives its fixed-deletion counting transfer. | Counting after a chosen deletion does not select a minimum-cost shared deletion set or establish the stated optimization bound. |
| Hu, Sun, Patwa, Panigrahi and Roy [4], Definition 3.1, p.230 | Aggregated deletion propagation removes at least a requested number of answers to one query, minimizing the number of deleted source tuples. | This older formulation is narrower than GDP. Its limitations cannot be used to claim that GDP lacks simultaneous exact counts or preservation. |

The final reachability paper is **Journal of Computer and System Sciences 144 (2024), article 103549**. Its forest theorems are 14 and 15; the MFCS 2021 predecessors are 12 and 13. Its Theorem 16, p.13, concerns non-strict traversal and timed feedback vertex number. These version and parameter distinctions matter.

The existing manuscript already credits the reachability and counting results in Section 9.1. The substantive addition in this companion is the GDP construction and the resulting narrower positioning.

<!-- pagebreak -->

## 2. Derived GDP encoding: exact counts are expressible

The following is a construction developed for this comparison, not a temporal example claimed by the GDP authors. It uses ordinary relational queries and therefore does not assume that timestamp inequalities are primitive syntax in their definition.

### Preserve event identity and strict timing

Apply forced deletions first and reserve their total cost. Let `E0` be the remaining events. Put one row per original ID into a unary relation `Event(id)`.

Precompute two fixed compatibility relations from the baseline history:

- `H2(i,j)` contains exactly the valid strictly increasing, root-ending two-event ID tuples.
- `H3(i,j,k)` contains exactly the valid strictly increasing, root-ending three-event ID tuples.

Their sizes are at most `M^2` and `M^3`, where `M` is the explicit event count. Precomputation performs comparisons on binary-encoded timestamps; it does not expand the numerical lifetime into a time grid. Protect every row of each compatibility relation by preserving its identity view at full cardinality.

Define the queries:

```text
Q2(i,j)   :- H2(i,j),   Event(i), Event(j).
Q3(i,j,k) :- H3(i,j,k), Event(i), Event(j), Event(k).
```

Every output retains all event IDs. Thus set semantics counts each distinct event tuple once, even when endpoints and timestamps are duplicated. Deleting one `Event` row simultaneously affects every tuple containing that event. For each mandatory keep event, preserve its singleton `Event` view. Forced deletions have already been removed from the baseline.

### Enforce one exact profile entry

For a candidate pair `(w2,w3)` with `T0 <= w2 <= N2` and `0 <= w3 <= N3`, impose both requirements for each `h` in `{2,3}`:

```text
Delete at least N_h - w_h outputs of Q_h.
Preserve at least w_h outputs of Q_h.
```

Since deleting input rows can only remove these outputs, the two inequalities force exactly `w_h` survivors. Omit any requirement with threshold zero, and omit protection for an empty compatibility relation; these impose no restriction and the published definition uses positive requirement vectors. Putting a query in both the deletion and preservation lists is allowed by the GDP framework. Minimize deletions in the `Event` identity view for the unit-cost case. Each feasible solution then corresponds to a legal original-event deletion set with the requested counts, and conversely.

### Recover the whole profile table

Solve for every candidate pair and retain each optimum and one attaining event set. There are at most `(R + 1)(N3 + 1) = O((M + 1)^5)` pairs. The compatibility relations and each instance have polynomial size. This derives the full unit-cost table through polynomially many GDP calls. It does **not** bound the time or memory needed to solve those calls in terms of `R`.

Consequently, simultaneous exact counts, preservation, identity-sensitive multiplicity, forced choices and full-table output are not sufficient separations from GDP expressibility. The restricted temporal structure may still enable a new algorithmic guarantee.

<!-- pagebreak -->

## 3. Weighted ILP extension and a useful diagnostic

### Direct witness formulation

Let `y_e` be a binary variable indicating that a baseline event survives. Fix `y_e = 1` for mandatory keep events. For every tuple `q` in `H2` or `H3`, let binary `z_q` indicate that the tuple survives. Impose:

```text
z_q <= y_e                         for every event e in q
z_q >= sum(y_e for e in q) - |q| + 1
sum(z_q for q in H2) = w2
sum(z_q for q in H3) = w3
```

Minimize:

```text
cost(forced deletions) + sum(c_e * (1 - y_e) for e in E0)
```

These inequalities make `z_q` the conjunction of the retained event decisions. They prevent double counting when several deleted events destroy the same tuple. All coefficients `c_e` retain their original binary encoding; no event is copied once per unit of monetary cost. Zero costs are permitted.

This is a transparent weighted extension of the witness-indicator approach. The literal GDP Definition 4.1 uses cardinalities in its objective. The weighted construction should therefore be presented explicitly, without claiming that its full binary-cost specification is already a stated GDP theorem. No ILP implementation or performance benchmark is supplied by this companion.

### Why generic LP integrality cannot be assumed

Consider two distinct unit-cost middle events `b1,b2`, both at time 0 from `v` to `u`, and one unit-cost final event `c` at time 1 from `u` to root `z`. This is an eligible depth-two history. Its baseline is `(N2,N3) = (2,0)`. Set `T0 = 1`, so `R = 1`, and ask for exact `(W2,W3) = (1,0)`.

An integral solution must delete exactly one middle event; its optimum cost is 1. Deleting the final event leaves zero two-walks and misses the target. In the linear relaxation of the displayed formulation, the assignment

```text
y_b1 = y_b2 = 1;  y_c = 1/2
z_(b1,c) = z_(b2,c) = 1/2
```

satisfies every displayed constraint with objective `1/2`. This is an algebraic diagnostic for this formulation. It rules out automatically treating its LP relaxation as integral on all eligible histories. It does not rule out stronger formulations, cutting planes, other GDP algorithms, or another polynomial method.

### The parameter transfer must also be proved

Take `n` optional unit-cost first events before one mandatory-retained middle/final pair, preserve that pair, and require zero triples. Then `R = 0`, while all `n` first events must be deleted. Thus a bound parameterized by deletion count need not become a bound parameterized by `R`.

GDP Section 6, Propositions 6.1-6.4, recovers particular tractable deletion-propagation variants. This comparison has not derived the manuscript's `2^{O(sqrt(R))} poly(L)` time and polynomial-space guarantee from those results. A formulation encoding and an algorithmic implication are separate claims requiring separate evidence.

<!-- pagebreak -->

## 4. Positioning and review priorities

### Suggested contribution wording

The manuscript studies a structured temporal deletion problem and claims an exact algorithm parameterized by the allowed loss of two-event walks. On explicit depth-three in-arborescences, its final-event grouping and chronological state yield every attainable minimum-cost two-/three-walk profile in `2^{O(sqrt(R))} poly(L)` time and polynomial space. The formulation relates to generalized deletion propagation; the candidate contribution is the specialized structural algorithm and complexity guarantee, together with the stated deletion-budget hardness result.

This wording should remain conditional on proof assessment and a sufficiently broad literature comparison. It avoids claiming to introduce exact deletion constraints, temporal counting, tree dynamic programming, or min-plus convolution.

### What would settle the remaining questions

| Priority | Concrete evidence needed |
|---|---|
| Proof review | An expert check of Lemmas 3.1-3.3 and 4.1, all Section 5 complexity accounting, and Appendix A's reduction in both directions. |
| Theorem comparison | A theorem-level search for prior ordered-incidence, query-optimization, or temporal algorithms implying the same bound; any proposed transfer must preserve costs, shared decisions and its parameter. |
| Practical comparison | A tested generic ILP baseline and controlled instances varying `R`, event count, branches, timestamp ties, and cost bit length, if practical efficiency is to be claimed. The current batch does not establish a speed advantage. |
| Manuscript revision | Incorporate this GDP relation, cite the primary paper, qualify the weighted extension, and focus the novelty statement on the specialized theorem. Keep the frozen snapshot distinct from that future revision. |

The reachability paper's first-arrival state alone does not determine tuple multiplicity: manuscript Appendix B.2 gives equal-reachability histories with different `W3`. That is a limited obstruction to a direct summary, not a proof that no reduction exists. Likewise, polynomial counting of a fixed retained history does not itself optimize deletion choices. These observations identify work that a transfer argument must do; they do not certify novelty.

## References and source scope

**[1]** Neha Makhija and Wolfgang Gatterbauer. *Is Integer Linear Programming All You Need for Deletion Propagation? A Unified and Practical Approach for Generalized Deletion Propagation.* PVLDB 18(8), 2667-2680 (2025). [DOI 10.14778/3742728.3742756](https://doi.org/10.14778/3742728.3742756). [Primary PDF](https://www.vldb.org/pvldb/vol18/p2667-makhija.pdf). [Author full version, arXiv:2411.17603](https://arxiv.org/abs/2411.17603). Published Definition 4.1 and Sections 5-6 were the main comparison targets.

**[2]** Hendrik Molter, Malte Renken and Philipp Zschoche. *Temporal reachability minimization: Delaying vs. deleting.* Journal of Computer and System Sciences 144, article 103549 (2024). [DOI 10.1016/j.jcss.2024.103549](https://doi.org/10.1016/j.jcss.2024.103549). The supplied final journal full text was inspected. The earlier [MFCS 2021 open version](https://doi.org/10.4230/LIPIcs.MFCS.2021.76) has different theorem numbers.

**[3]** Jessica Enright, Kitty Meeks and Hendrik Molter. *Counting Temporal Paths.* Algorithmica 87, 736-782 (2025). [DOI 10.1007/s00453-025-01301-3](https://doi.org/10.1007/s00453-025-01301-3). [Author-hosted final article](https://eprints.gla.ac.uk/348161/1/348161.pdf). Theorem 2 is on printed p.754.

**[4]** Xiao Hu, Shouzhuo Sun, Shweta Patwa, Debmalya Panigrahi and Sudeepa Roy. *Aggregated Deletion Propagation for Counting Conjunctive Query Answers.* PVLDB 14(2), 228-240. [DOI 10.14778/3425879.3425892](https://doi.org/10.14778/3425879.3425892). [Primary PDF](https://vldb.org/pvldb/vol14/p228-hu.pdf). This comparison uses Definition 3.1; the volume/pages and DOI identify the article despite differing online/issue year conventions.

The broader sources already discussed in manuscript Section 9, including set-cover and other optimization frameworks, remain relevant. This companion does not replace that bibliography or claim to have eliminated every potential subsumption route. No correspondence or approval from the cited authors is assumed.

