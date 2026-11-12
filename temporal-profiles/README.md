# Minimum-Cost Temporal Walk Profiles

**Author: Goutam Dyapa**  
**Manuscript: Minimum-Cost Temporal Walk Profiles on Depth-Three In-Arborescences**  
**Snapshot: working manuscript dated 5 November 2026**

This directory contains the manuscript, exact profile solver, frozen correctness material,
and synthetic transaction experiments for the temporal-profile study. It is a separate
study from the Elliptic++ prediction models documented at the repository root.

## Read the paper

- [Current 27-page manuscript](manuscript/Goutam_Dyapa_Temporal_Walk_Profiles.pdf)
- [LaTeX source](manuscript/source/main.tex)
- [Two-page Mac batch findings](docs/MAC_BATCH_FINDINGS.pdf)
- [Results and limitations](docs/RESULTS.md)
- [Reproduction and evidence provenance](docs/REPRODUCIBILITY.md)

## What the algorithm does

For a temporal transaction history whose static graph is a directed tree toward a
designated root, with depth at most three, the solver finds the minimum deletion cost
for every attainable pair of two-event and three-event walk counts ending at that root.
It preserves a specified lower bound on the two-event count. Timestamps must increase
strictly; distinct event IDs remain separate decisions, including parallel events.
Nonnegative integer deletion costs and mandatory keep/delete choices are supported.

The manuscript states a running-time bound of `2^{O(sqrt(R))} poly(L)`, where `R` is
the allowed loss in two-event walks after mandatory deletions, and `L` is the explicit
input length. It separately establishes hardness in the deletion-budget parameter.
These are different parameters. The accompanying implementation and finite checks
do not replace independent assessment of the proofs or prior-art positioning.

The returned table supports exact targets as well as upper bounds. An exact count can
be unattainable even when a smaller count is cheap to obtain. A general fraud model
may use other features changed by deletions; this table alone does not establish a
change in that model's prediction.

## Quick start on macOS

Python 3.8 or newer is required. The solver uses only the Python standard library;
the transaction runner also uses its standard `sqlite3` module. No pip install is needed.

From the repository root:

```bash
cd temporal-profiles
python3 implementation/demo.py
python3 implementation/profile_solver.py implementation/examples/nonmonotone.json --output result.json
```

The four bundled examples cover exact-target selection, weighted deletions, parallel
final events, and mandatory deletions. [Mac instructions](docs/REPRODUCIBILITY.md)
also describe the native batch runner and the optional full correctness check.

## Inspect the completed experiment

No dataset download or solver run is needed to inspect the saved aggregate results:

```bash
python3 analysis/summarize_batch.py results/BATCH_RESULTS.zip
```

The fixed cohort contains **1,024 queries**: 179 empty contexts, 280 unsupported
contexts, 43 supported contexts above the event cap, and 522 fully profiled contexts.
Among the 232 queries with a positive initial three-event count, 68 received complete
profiles. At full two-event preservation, all 68 reached the upper-bound target within
three unit-cost deletions; only 13 reached the exact target, and 55 exact targets were
unattainable. See [the complete denominators and verification limits](docs/RESULTS.md).

The data are synthetic. These results describe count-constrained deletion problems,
not measured fraud-detection or money-laundering prevention effectiveness.

## Directory guide

| Directory | Contents |
|---|---|
| `manuscript/` | Current named PDF and LaTeX source |
| `implementation/` | Unchanged solver, examples, validator, frozen corpus and protocol |
| `batch/` | Unchanged native batch runtime, frozen cohort/protocols, small demonstration and existing tests |
| `illustration/` | Separate frozen ten-event mathematical illustration |
| `results/` | Original Mac aggregate export and its descriptive reaggregation |
| `analysis/` | Portable aggregate-checking script |
| `evidence/` | Original Mac correctness summary and retained reference validation archive |
| `docs/` | Reproduction instructions, results, data requirements and short findings note |

## Integrity and citation

```bash
python3 verify_artifacts.py
```

This checks the SHA-256 manifest of this directory; it does not execute experiments.
The preserved solver digest is
`a9f8f2c9f276055ab570940d784244192d177c16299f7a295ad75c481de7f4ba`.

Use the [study-specific CITATION.cff](CITATION.cff) when citing this artifact. The root
repository citation describes the separate counterfactual fraud-network study.
The included manuscript is a working manuscript. The comparison with generalized
deletion propagation remains a follow-up item; this snapshot does not claim that all
prior-art questions are resolved.

Goutam Dyapa ran the reported macOS experiments. ChatGPT assisted with manuscript
drafting and revision, code development, and validation tasks, as disclosed in the paper.
