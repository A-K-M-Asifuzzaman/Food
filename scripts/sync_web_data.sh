#!/usr/bin/env bash
# Copy the report JSONs the web app renders into web/data so the frontend
# deploys to Vercel without needing the repository's artifacts/ tree, which is
# gitignored and far too large to ship.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p web/data/reports web/public/data
cp artifacts/reports/{calibration_ensemble_siglip_eva02,calibration_siglip_so400m,conformal,ensemble,rag_evaluation}.json web/data/reports/
cp artifacts/reports/probe_*.json web/data/reports/
cp data/nutrition/kb.json web/data/kb.json
cp artifacts/index/graph.json web/public/data/graph.json
echo "synced $(ls web/data/reports | wc -l | tr -d ' ') reports, kb.json and graph.json"
