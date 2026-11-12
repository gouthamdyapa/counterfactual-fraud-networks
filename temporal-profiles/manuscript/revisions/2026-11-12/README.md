# Temporal Walk Profiles: 12 November 2026 revision

**Author: Goutam Dyapa**  
**Status: working manuscript, 30 pages**

[Read the revised manuscript](Goutam_Dyapa_Temporal_Walk_Profiles_2026-11-12.pdf) | [LaTeX source](source/main.tex) | [Download source package](Temporal_Walk_Profiles_Source_2026-11-12.zip) | [Citation](CITATION.bib)

## What this revision changes

This revision incorporates the generalized deletion propagation (GDP) comparison into the manuscript. The abstract, introduction, related work, and conclusion now distinguish the formulation's expressibility from the specialized preservation-loss algorithm and its stated `2^{O(sqrt(R))} poly(L)` time and polynomial-space guarantee.

The added related-work subsection cites Makhija and Gatterbauer's [published GDP paper](https://doi.org/10.14778/3742728.3742756). New Appendix E provides:

- A polynomial-size encoding of each unit-cost exact profile entry using protected compatibility relations and original event IDs.
- A proof that the encoding preserves feasibility, minimum optional deletion count, and attaining witnesses, including mandatory statuses and zero-threshold edge cases.
- An explicit weighted ILP formulation retaining binary deletion-cost coefficients.
- The polynomial bound on the number of target pairs needed to recover the complete profile table.
- A small fractional-relaxation example, limited to the displayed formulation.

The source also clarifies which cohort data are public and which native-run diagnostics are absent from the aggregate export. The author name and existing research-workflow disclosure are retained.

## Relationship to the frozen study

The [5 November manuscript](../../Goutam_Dyapa_Temporal_Walk_Profiles.pdf), its source, and the [frozen study checksum manifest](../../../MANIFEST.sha256) remain unchanged. The earlier theorem/proof blocks, hardness and counting appendices, solver, correctness corpus, and reported transaction experiments have not been revised or rerun for this manuscript update. The new GDP encoding proposition is an additional comparison result.

This is a versioned manuscript revision, not a report of new experiments, independent human proof review, journal acceptance, or guaranteed originality. A broader theorem-level comparison and specialist proof assessment remain relevant.

The [eight-page reviewer companion](../../../review/REVIEWER_GUIDE.md) explicitly maps the 5 November, 27-page snapshot. Use the [updated review map](REVIEW_MAP.md) for this revision's pagination. Existing theorem numbers and Appendices A-D are preserved; Appendix E is new.

## Build on a Mac

The supplied PDF needs no build. To regenerate it, a working LaTeX distribution with `latexmk`, pdfLaTeX, BibTeX, and the packages imported by `source/main.tex` is required. From this revision directory:

```bash
bash build_mac.command
```

The regenerated file is `build/main.pdf`. The script does not run the profile solver or transaction experiments and does not overwrite the supplied PDF. Generated build files are excluded from the source archive.

To check the downloaded revision's file identities on a Mac, run from this directory:

```bash
shasum -a 256 -c SHA256SUMS
```

The checksums identify the supplied files. A local PDF rebuild can have different metadata and therefore a different byte digest. The source ZIP contains the LaTeX files, this README, review map, citation, and Mac build script; it omits the supplied PDF and outer checksum manifest.

For the unchanged solver and saved-result checks, use the [study reproduction guide](../../../docs/REPRODUCIBILITY.md).

## Citation

Use [CITATION.bib](CITATION.bib) to identify this dated manuscript revision. The study-level `CITATION.cff` continues to identify the frozen research artifact and its original manuscript snapshot.

Goutam Dyapa ran the reported macOS experiments. ChatGPT assisted with manuscript drafting and revision, code development, and validation tasks, as disclosed in the manuscript.
