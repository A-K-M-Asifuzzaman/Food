#!/usr/bin/env bash
# Build the proposal PDF. Tectonic fetches whatever TeX packages it needs on
# first run, so the initial build is slow and needs a network connection.
set -e
cd "$(dirname "$0")"
tectonic proposal.tex
echo "wrote $(pwd)/proposal.pdf"
