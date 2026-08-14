# Data

Raw Elliptic++ data and large prepared arrays are intentionally **not committed** to Git.

## Raw files used by the paper
Place the authoritative Elliptic++ files in `data/raw/` using the filenames recorded in `raw_manifest.json`.
Verify them with:

```bash
sha256sum -c data/raw_manifest.sha256
```

The final paper experiments use the wallet feature/class files and the five-part `AddrAddr` graph. `AddrTx`/`TxAddr` files were integrity-checked during development but are not required by the final models reported in the paper.

## Generated prepared arrays
The following large arrays were generated during the experiments and are excluded from Git because of size:

- `temf_prepared.npz`
- `temf_graph_structural_prepared.npz`
- `temf_final_graph_prepared.npz`

Their sizes and SHA-256 digests are recorded in `prepared_artifacts_manifest.json`.

## Labels
The supervised task uses Elliptic++ labeled wallets only. Unknown labels are excluded from supervised evaluation and are not converted to negative examples.

## Chronological split
- Train: time steps 1–34
- Validation: 35–41
- Test: 42–49
