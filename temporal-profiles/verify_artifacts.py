#!/usr/bin/env python3
"""Check the research snapshot's file hashes without executing experiments."""
import hashlib
from pathlib import Path, PurePosixPath
import sys


def main():
    root = Path(__file__).resolve().parent
    failures = []
    count = 0
    for line in (root / 'MANIFEST.sha256').read_text(encoding='utf-8').splitlines():
        expected, relative = line.split('  ', 1)
        path = PurePosixPath(relative)
        if path.is_absolute() or '..' in path.parts:
            failures.append('Invalid manifest path: ' + relative)
            continue
        target = root.joinpath(*path.parts)
        if not target.is_file():
            failures.append('Missing: ' + relative)
        elif hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            failures.append('Changed: ' + relative)
        count += 1
    if failures:
        print('\n'.join(failures), file=sys.stderr)
        return 1
    print('Verified {} research artifact files. No experiments were run.'.format(count))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
