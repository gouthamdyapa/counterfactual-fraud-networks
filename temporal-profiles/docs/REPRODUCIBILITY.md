# Reproduction and evidence provenance

All commands below start in `temporal-profiles/` unless a different directory is
shown. Python 3.8+ is sufficient, including the Mac Python 3.9.6 used for the
reported native runs. The solver and batch runner require no third-party packages.
The batch runner needs the standard-library `sqlite3` module.

## Check the artifact without running experiments

```bash
python3 verify_artifacts.py
python3 analysis/summarize_batch.py results/BATCH_RESULTS.zip
```

The first command checks this snapshot's file hashes. The second reconciles the
saved five-file aggregate export and prints descriptive results. Neither command
needs the original transaction dataset or executes a solver experiment.

## Small examples

```bash
python3 implementation/demo.py
python3 implementation/profile_solver.py implementation/examples/nonmonotone.json --output result.json
bash batch/run_batch.command demo
```

The standalone demonstration uses four bundled instances. The batch demonstration
uses a small bundled CSV and deliberately includes empty, unsupported, and capped
contexts; its expected status is `completed_with_limits`. Its final check should
report `Synthetic batch demonstration: PASS`. A `.command` file can also be run
through Terminal with `bash` without changing macOS security settings.

## Optional native IBM batch reproduction

The reported 1,024-query run is complete; reproducing it is optional. Obtain the
exact original dataset described in [DATA.md](DATA.md), then run:

```bash
bash batch/run_batch.command run --csv "/full/path/to/HI-Small_Trans.csv"
```

To reuse the compatible cache from an earlier pilot:

```bash
bash batch/run_batch.command run --csv "/full/path/to/HI-Small_Trans.csv" --cache-dir "/full/path/to/temporal_profile_mac_pilot/cache"
```

The interactive launcher is also available:

```bash
bash batch/run_batch.command
```

It asks for the CSV or a compatible pilot folder when needed. The source CSV is
read-only. The program makes no network requests or automatic uploads. New run
artifacts and caches are local and excluded by this directory's `.gitignore`.
For pause/resume, press Control+C once and let the runner write its checkpoint.
Restart the same command; it reuses matching completed records. `--new-run`
explicitly requests another output folder.

The frozen policy and resource limits are in `batch/batch_protocol.json`.
`SOURCE_COHORT_PROTOCOL.json` records the earlier sampling audit; that earlier
audit's optimization variants are not the protocol of this completed batch.
The bundled `cohort.json` preserves synthetic bank/account identifiers and cutoff
minutes needed to reproduce the exact cohort.

## Optional correctness rerun

The separate correctness suite uses the frozen corpus adjacent to the validator:

```bash
python3 implementation/validate_profiles.py --run --candidate implementation/profile_solver.py
```

Use `--run` for this existing corpus. `--prepare` and `--amend-root-endpoint` are
historical construction modes and must not be used to replace the frozen evidence.
The validator enumerates original event tuples and legal deletion subsets, without
calling the solver's counting, grouping, or optimization helpers. It checks the
complete attainable table, costs, witnesses, selection rules, and invalid inputs.
This computational separation does not imply a separate human review.

The separate ten-event mathematical illustration can be checked with:

```bash
python3 illustration/check_illustration.py --solver-path implementation/profile_solver.py --output illustration/recheck.json
```

## Retained evidence

`evidence/reference_validation.zip` preserves every file in the original retained
`validation_results/` directory, without changing its bytes or relative paths.
Its accompanying manifest records each member digest. It includes the initial
failed run, the documented correction of the root-ending counting specification,
both frozen snapshots, successful reference runs, and their full outputs.
The current reference run is
`run_20261104T071237.909200Z_a9f8f2c9f276`.

`evidence/MAC_VALIDATION_RESULTS.json` is the unchanged native Mac correctness
summary, renamed from its original upload filename. Its digest is
`26eb54eaebed908e15fe45371c48f7b9703eb8838b30ad9900c67af82d7f574f`.
It records 375 histories, 1,863 threshold calls, 2,529 profile entries, 54,076
selection queries, and no mismatch. Recorded output digests match the retained
reference output bytes. Full native output files were not independently rehashed.

Historical machine paths and process-metadata field names remain in these frozen
records. They describe the recorded run, not portable paths to use now. Fields
about an oracle author are historical agent-workflow metadata, not evidence of
independent human authorship or external scientific review. The current manuscript
states the actual roles and the checker's concrete behavior.

The runnable solver, validator, corpus, protocols, batch runtime, examples, and
result export were copied byte-for-byte from the frozen releases. The new README,
guides, citation, directory structure, archive container, and manifest are repository
packaging. Obsolete supplements and internal editorial review files are omitted.
The new manifest checks only this snapshot; an old whole-release manifest is not
represented as validating this rearranged directory.

## Build the paper

With a LaTeX installation containing `latexmk`:

```bash
cd manuscript/source
latexmk -pdf main.tex
```

This builds `main.pdf` without running experiments. The prebuilt named PDF in the
parent directory is the existing 5 November 2026 review copy.

## Scope of this GitHub update

This update packages existing research and evidence. It does not add a new dataset
run or change the frozen algorithm. The 27-page theory manuscript is distinct from
the root repository's fraud-prediction manuscript. A detailed comparison with the
generalized deletion propagation framework remains pending; the present snapshot
does not claim a completed novelty review.
