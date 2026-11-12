#!/bin/bash
set -euo pipefail

revision_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v latexmk >/dev/null 2>&1; then
  printf '%s\n' 'This optional manuscript build requires latexmk and a working LaTeX distribution.'
  printf '%s\n' 'The supplied PDF can be read without installing LaTeX.'
  exit 1
fi

mkdir -p "$revision_dir/build"
(
  cd "$revision_dir/source"
  latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error \
    -pdflatex='pdflatex -no-shell-escape %O %S' \
    -outdir="$revision_dir/build" main.tex
)

printf '\nBuilt manuscript: %s/build/main.pdf\n' "$revision_dir"
