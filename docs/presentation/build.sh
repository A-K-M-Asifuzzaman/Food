#!/usr/bin/env bash
# Figures are shared with the paper rather than duplicated, so building the
# paper first guarantees the two cannot disagree about a number.
set -e
cd "$(dirname "$0")"
../../.venv/bin/python ../paper/figures.py > /dev/null
tectonic slides.tex
echo "wrote $(pwd)/slides.pdf"
