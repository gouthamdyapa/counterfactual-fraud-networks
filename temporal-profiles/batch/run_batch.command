#!/bin/bash
# Local batch launcher: uses an existing Python and performs no installation.
set -u

batch_dir="$(CDPATH= cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)" || exit 1
cd "$batch_dir" || exit 1

if [ ! -f "$batch_dir/batch.py" ]; then
    printf '%s\n' 'batch.py is missing. Extract the complete batch ZIP into one folder, then run this launcher again.' >&2
    exit 1
fi

batch_python_works() {
    [ -n "$1" ] || return 1
    "$1" -c 'import sys
if sys.version_info < (3, 8):
    raise SystemExit(1)
import sqlite3
' >/dev/null 2>&1
}

batch_python=''
if [ -n "${TEMPORAL_BATCH_PYTHON:-}" ]; then
    if batch_python_works "$TEMPORAL_BATCH_PYTHON"; then
        batch_python="$TEMPORAL_BATCH_PYTHON"
    else
        printf '%s\n' 'TEMPORAL_BATCH_PYTHON is unavailable or lacks Python 3.8+ / sqlite3 support; checking python3.' >&2
    fi
fi

if [ -z "$batch_python" ] && batch_python_works python3; then
    batch_python='python3'
fi

if [ -z "$batch_python" ] && [ -n "${HOME:-}" ]; then
    batch_existing_python="$HOME/Projects/PACT_MAC_FULL/.venv/bin/python"
    if batch_python_works "$batch_existing_python"; then
        batch_python="$batch_existing_python"
    fi
fi

if [ -z "$batch_python" ]; then
    printf '%s\n' \
        'A compatible existing Python was not found.' \
        'This batch requires Python 3.8 or newer with its standard sqlite3 module.' \
        'Set TEMPORAL_BATCH_PYTHON to the full path of a compatible Python, then rerun.' \
        'Example: TEMPORAL_BATCH_PYTHON="/full/path/to/python3" bash run_batch.command' >&2
    exit 1
fi

printf '%s\n' 'TEMPORAL PROFILE — NATIVE MAC BATCH'
printf 'Using Python: %s\n' "$batch_python"

batch_interactive=0
if [ "$#" -eq 0 ]; then
    batch_interactive=1
    set -- interactive
fi

"$batch_python" -B "$batch_dir/batch.py" "$@"
batch_exit_code=$?

# Keep a Finder-launched Terminal readable. Explicit CLI commands do not pause.
if [ "$batch_interactive" -eq 1 ] && [ -t 0 ] && [ -t 1 ]; then
    printf '\n%s' 'Press Return to close this launcher. '
    IFS= read -r batch_finished || true
fi

exit "$batch_exit_code"
