#!/usr/bin/env bash
# Regenerate the figures from the evaluation artifacts, then build the PDF.
# Running figures.py first is deliberate: a figure that drifts from the result
# it claims to show is worse than no figure.
set -e
cd "$(dirname "$0")"
../../.venv/bin/python figures.py
tectonic paper.tex
echo "wrote $(pwd)/paper.pdf"
