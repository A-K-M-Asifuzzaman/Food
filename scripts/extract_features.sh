#!/usr/bin/env bash
# Build the frozen feature bank, one backbone at a time.
#
# Sequential on purpose: each backbone alone peaks around 3-4 GB of unified
# memory, and running two at once on an 18 GB machine pushes the whole desktop
# into swap. Batch size 8 is what the benchmark validated - larger batches gain
# almost nothing on MPS and raise the odds of a mid-run OOM on a job this long.
set -u

cd "$(dirname "$0")/.." || exit 1
mkdir -p artifacts/reports

for key in siglip_so400m eva02_large dinov2_large; do
  log="artifacts/reports/extract_${key}.log"
  echo "=== ${key} started $(date -u +%FT%TZ) ===" | tee -a "$log"
  # -u keeps stdout unbuffered: without it Python block-buffers when redirected
  # to a file and the dashboard sees nothing until the process exits.
  .venv/bin/python -u -m nutrivision.models.features \
    --backbones "$key" \
    --splits train test \
    --batch-size 8 \
    --workers 6 >>"$log" 2>&1
  status=$?
  echo "=== ${key} exit=${status} $(date -u +%FT%TZ) ===" | tee -a "$log"
  if [ "$status" -ne 0 ]; then
    echo "ABORT: ${key} failed, leaving remaining backbones untouched" | tee -a "$log"
    exit "$status"
  fi
done

echo "FEATURE_BANK_COMPLETE $(date -u +%FT%TZ)"
