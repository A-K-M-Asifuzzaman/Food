#!/usr/bin/env python3
"""Assemble and upload the inference service to its Hugging Face Space."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ID = "AsifZaman1912/prac"

# Everything the container needs, and nothing else.
PAYLOAD: list[str] = [
    "backend/app",
    "backend/requirements.txt",
    "src/nutrivision",
    "data/nutrition/kb.json",
    "data/nutrition/corpus.jsonl",
    "artifacts/checkpoints/probe_siglip_so400m.pt",
    "artifacts/checkpoints/probe_eva02_large.pt",
    "artifacts/index/documents.jsonl",
    "artifacts/index/embeddings.npy",
    "artifacts/index/bm25.pkl",
    "artifacts/index/manifest.json",
    "artifacts/reports/conformal.json",
    "artifacts/reports/calibration_ensemble_siglip_eva02.json",
]

EXCLUDE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", ".ipynb_checkpoints")

# Routes that must exist in the uploaded service.
REQUIRED_ROUTES = ["/predict", "/explain", "/ask", "/health", "/warm", "/stats", "/feedback"]


def build(stage: Path) -> None:
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    missing = []
    for rel in PAYLOAD:
        src = ROOT / rel
        dst = stage / rel
        if not src.exists():
            missing.append(rel)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, ignore=EXCLUDE)
        else:
            shutil.copy2(src, dst)

    if missing:
        sys.exit("missing from the payload:\n  " + "\n  ".join(missing))

    shutil.copy2(ROOT / "backend/Dockerfile", stage / "Dockerfile")
    (stage / "README.md").write_text(SPACE_README)


def verify(stage: Path) -> None:
    """Cheap checks that catch the failures actually seen on this deployment."""
    main = (stage / "backend/app/main.py").read_text()
    absent = [r for r in REQUIRED_ROUTES if f'"{r}"' not in main]
    if absent:
        sys.exit(f"main.py declares no route for: {', '.join(absent)}")

    reqs = (stage / "backend/requirements.txt").read_text()
    for pkg in ["sentence-transformers", "rank-bm25", "openai", "timm", "torch"]:
        if pkg not in reqs:
            sys.exit(f"requirements.txt does not pin {pkg}")

    index = stage / "artifacts/index/documents.jsonl"
    if index.stat().st_size < 10_000:
        sys.exit("retrieval index looks truncated")

    # Uploading a file to the Space repo does not put it in the container.
    dockerfile = (stage / "Dockerfile").read_text()
    copied = " ".join(
        line for line in dockerfile.splitlines() if line.startswith("COPY")
    )
    uncopied = [
        rel for rel in PAYLOAD
        if not rel.startswith("backend/")
        and rel not in copied
        and str(Path(rel).parent) not in copied
    ]
    if uncopied:
        sys.exit(
            "the Dockerfile does not COPY these payload files, so they will be "
            "uploaded but absent from the running container:\n  "
            + "\n  ".join(uncopied)
        )

    total = sum(f.stat().st_size for f in stage.rglob("*") if f.is_file())
    print(f"payload verified — {total / 1e6:.1f} MB across "
          f"{sum(1 for f in stage.rglob('*') if f.is_file())} files")


SPACE_README = """---
title: FoodGenome AI
emoji: 🕸️
colorFrom: red
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Food-101 classifier with conformal sets and grounded RAG
---

# FoodGenome AI — inference service.

FastAPI service behind [the web app](https://food-red-omega.vercel.app).

Two-backbone ensemble (SigLIP-SO400M + EVA-02-L), 97.16% top-1 on the Food-101
test split, temperature-scaled, with split-conformal prediction sets at 99.6%
measured coverage and a nutrition RAG pipeline grounded in USDA figures.

Interactive docs at `/docs`. The container sleeps when idle; the first request
after that pays roughly thirty seconds of model load.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stage", default=None, help="where to assemble the payload")
    args = ap.parse_args()

    stage = Path(args.stage) if args.stage else ROOT / ".space-build"
    build(stage)
    verify(stage)

    if args.dry_run:
        print(f"dry run — payload left at {stage}")
        return

    from huggingface_hub import HfApi

    api = HfApi()
    print(f"uploading to {REPO_ID} as {api.whoami()['name']}…")
    api.upload_folder(
        folder_path=str(stage),
        repo_id=REPO_ID,
        repo_type="space",
        commit_message="Deploy inference service",
        delete_patterns="*",  # remove files no longer in the payload
    )
    print(f"done — https://huggingface.co/spaces/{REPO_ID}")


if __name__ == "__main__":
    main()
