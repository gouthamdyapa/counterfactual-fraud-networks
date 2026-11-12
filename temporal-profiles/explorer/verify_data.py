#!/usr/bin/env python3
"""Read-only verification of the explorer's complete packaged reference data.

Recompute the five small fixture tables with the unchanged solver, independently
check all legal deletion subsets and witnesses, and compare the serialized data.
This command does not overwrite the data or rerun the IBM transaction batch.
"""

from __future__ import annotations

import json
import sys

from generate_data import DATA_PATH, build_data, encode_data, sha256_bytes


def main() -> int:
    try:
        data = build_data()
        expected = encode_data(data)
        packaged = DATA_PATH.read_bytes()
        if packaged != expected:
            raise AssertionError(
                "data.js differs from verified source outputs; run generate_data.py "
                "and inspect the resulting changes before committing"
            )
    except (OSError, ValueError, AssertionError) as exc:
        print("Explorer data verification: FAIL: {}".format(exc), file=sys.stderr)
        return 1
    print("Explorer data verification: PASS")
    print(json.dumps(data["verification"], indent=2, sort_keys=True))
    print("Solver SHA-256: {}".format(data["source"]["solver_sha256"]))
    print("data.js SHA-256: {}".format(sha256_bytes(packaged)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
