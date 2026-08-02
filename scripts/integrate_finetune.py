"""Validate and integrate the Kaggle fine-tune, then say whether it actually helped.

Run this after dropping the Kaggle outputs into `artifacts/`. It refuses to
report anything until the exported logits are proven to describe the same images
in the same order as the local labels.

That check is the point of the script. Row-order drift between two machines is
silent: the arrays have the right shape, every downstream script runs happily,
and the ensemble numbers are meaningless. Recomputing accuracy from the logits
and comparing it against the figure Kaggle printed catches it immediately —
misaligned rows collapse accuracy to roughly chance, which is impossible to
mistake for a real result.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

import numpy as np

from nutrivision.config import CHECKPOINT_DIR, REPORT_DIR

LOGIT_DIR = REPORT_DIR / "logits"
MEMBER = "eva02_ft"
FROZEN_BEST = 97.156


def fail(message: str) -> None:
    print(f"\n  FAILED: {message}")
    sys.exit(1)


def check_present() -> dict:
    expected = {
        "val logits": LOGIT_DIR / f"probe_{MEMBER}_val.npy",
        "test logits": LOGIT_DIR / f"probe_{MEMBER}_test.npy",
    }
    optional = {
        "result json": REPORT_DIR / "eva02_ft_result.json",
        "checkpoint": CHECKPOINT_DIR / "eva02_large_448_last.pt",
    }
    missing = [name for name, p in expected.items() if not p.exists()]
    if missing:
        print("Expected files, not found:")
        for name in missing:
            print(f"  {name:<12} -> {expected[name]}")
        fail("copy the Kaggle outputs into artifacts/ first (see kaggle/README.md section 6)")

    for name, path in optional.items():
        print(f"  {'found' if path.exists() else 'absent':<7} {name}: {path.name}")
    return {"expected": expected, "optional": optional}


def validate_alignment() -> dict:
    val = np.load(LOGIT_DIR / f"probe_{MEMBER}_val.npy")
    test = np.load(LOGIT_DIR / f"probe_{MEMBER}_test.npy")
    val_y = np.load(LOGIT_DIR / "val_y.npy")
    test_y = np.load(LOGIT_DIR / "test_y.npy")

    print(f"\n  val  logits {val.shape}   labels {val_y.shape}")
    print(f"  test logits {test.shape}   labels {test_y.shape}")

    if val.shape[0] != val_y.shape[0] or test.shape[0] != test_y.shape[0]:
        fail("row counts differ from the local labels — wrong split or a truncated export")
    if val.shape[1] != 101 or test.shape[1] != 101:
        fail(f"expected 101 classes, got {val.shape[1]}")

    val_acc = float((val.argmax(1) == val_y).mean() * 100)
    test_acc = float((test.argmax(1) == test_y).mean() * 100)
    print(f"\n  recomputed val top-1  {val_acc:.3f}")
    print(f"  recomputed test top-1 {test_acc:.3f}")

    if test_acc < 20.0:
        fail(
            f"test accuracy {test_acc:.2f}% is near chance (1/101 = 0.99%). The logits are "
            "almost certainly in a different row order than the local labels — the class "
            "list or the file ordering diverged. Do not use these numbers."
        )

    reported = None
    result_path = REPORT_DIR / "eva02_ft_result.json"
    if result_path.exists():
        reported = json.loads(result_path.read_text()).get("test_top1")
        if reported is not None:
            drift = abs(reported - test_acc)
            print(f"  Kaggle reported       {reported:.3f}   (drift {drift:.3f})")
            if drift > 0.5:
                fail(
                    "recomputed accuracy disagrees with what Kaggle printed by more than "
                    "0.5 points, so the exported logits are not the ones that produced "
                    "that figure"
                )

    print("\n  alignment verified")
    return {"val_top1": val_acc, "test_top1": test_acc, "reported": reported}


def run(cmd: list[str]) -> None:
    print(f"\n$ {' '.join(cmd)}\n")
    subprocess.run(cmd, check=False)


def main() -> None:
    p = argparse.ArgumentParser(description="Integrate the Kaggle fine-tune")
    p.add_argument("--python", default=".venv/bin/python")
    p.add_argument("--skip-downstream", action="store_true")
    args = p.parse_args()

    print("── files ──")
    check_present()

    print("\n── alignment ──")
    stats = validate_alignment()

    print("\n── verdict ──")
    solo = stats["test_top1"]
    print(f"  fine-tune alone   {solo:.3f}")
    print(f"  frozen ensemble   {FROZEN_BEST:.3f}")
    if solo > FROZEN_BEST:
        print(f"  the fine-tune beats the frozen pair by {solo - FROZEN_BEST:+.3f} on its own")
    else:
        print(
            f"  {FROZEN_BEST - solo:.3f} short on its own — which does not settle it. The "
            "question is whether its errors decorrelate enough to help in combination."
        )

    if args.skip_downstream:
        return

    run([args.python, "-m", "nutrivision.training.ensemble",
         "--members", "siglip_so400m", "eva02_large", MEMBER,
         "--name", "ensemble_with_finetune"])
    run([args.python, "-m", "nutrivision.reliability.conformal",
         "--members", "siglip_so400m", MEMBER, "--name", "conformal_with_finetune"])

    print(
        "\nThe ensemble table above is the answer. Read the McNemar line, not the "
        "accuracy column: a few tenths on 25,250 images is inside the range where two "
        "systems differ by luck."
    )


if __name__ == "__main__":
    main()
