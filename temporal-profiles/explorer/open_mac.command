#!/bin/bash
set -euo pipefail

EXPLORER_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(uname -s)" != "Darwin" ]]; then
    printf 'Open %s/index.html in your web browser. This launcher is for macOS.\n' "$EXPLORER_DIR"
    exit 1
fi
open "$EXPLORER_DIR/index.html"
