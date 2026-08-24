"""Push, run and monitor the fine-tune kernel on Kaggle from the command line."""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

from nutrivision.config import CHECKPOINT_DIR, REPORT_DIR

KERNEL_DIR = Path(__file__).resolve().parents[1] / "notebooks" / "kaggle"
REF = "asifxzaman/foodgenome-eva02-finetune"

# Where each Kaggle output belongs locally.
PLACEMENT = {
    "probe_eva02_ft_val.npy": REPORT_DIR / "logits",
    "probe_eva02_ft_test.npy": REPORT_DIR / "logits",
    "eva02_ft_result.json": REPORT_DIR,
    "eva02_large_448_last.pt": CHECKPOINT_DIR,
}

TERMINAL = {"complete", "error", "cancelled", "cancelAcknowledged"}


def api():
    from kaggle.api.kaggle_api_extended import KaggleApi

    client = KaggleApi()
    client.authenticate()
    return client


def status_of(client) -> tuple[str, str | None]:
    try:
        s = client.kernels_status(REF)
    except Exception as exc:  # noqa: BLE001 - surfacing the API message is the point
        if "404" in str(exc):
            return "not-committed", (
                "no committed version exists. An interactive run is invisible to the API; "
                "use `push` to start a committed one."
            )
        return "unknown", str(exc)[:200]
    raw = getattr(s, "status", s)
    return str(raw), getattr(s, "failureMessage", None)


def cmd_push(client, args) -> None:
    print(f"pushing {KERNEL_DIR} -> {REF}")
    if not (KERNEL_DIR / "kernel-metadata.json").exists():
        sys.exit("kernel-metadata.json missing")
    result = client.kernels_push(str(KERNEL_DIR))
    print("  ref     :", getattr(result, "ref", REF))
    print("  version :", getattr(result, "versionNumber", "?"))
    if getattr(result, "error", None):
        sys.exit(f"  error: {result.error}")
    print(f"\nrunning. https://www.kaggle.com/code/{REF}")
    print("Poll it with:  python scripts/kaggle_run.py watch")


def cmd_status(client, args) -> None:
    state, message = status_of(client)
    print(f"{REF}: {state}")
    if message:
        print(f"  {message}")


def cmd_watch(client, args) -> None:
    started = time.time()
    last = None
    while True:
        state, message = status_of(client)
        elapsed = time.time() - started
        if state != last:
            print(f"[{elapsed/60:6.1f} min] {state}" + (f" — {message}" if message else ""))
            last = state
        if state in TERMINAL:
            if state == "complete":
                print("\nfinished. fetch the outputs with:  python scripts/kaggle_run.py fetch")
            return
        if state == "not-committed":
            return
        time.sleep(args.interval)


def cmd_fetch(client, args) -> None:
    dest = Path(args.into)
    dest.mkdir(parents=True, exist_ok=True)
    print(f"downloading outputs to {dest}")
    client.kernels_output(REF, path=str(dest), force=True, quiet=False)

    moved = 0
    for name, target in PLACEMENT.items():
        found = next(dest.rglob(name), None)
        if not found:
            print(f"  missing  {name}")
            continue
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(found, target / name)
        size = (target / name).stat().st_size / 2**20
        print(f"  placed   {name:<32} -> {target}  ({size:.1f} MB)")
        moved += 1

    if moved:
        print("\nNow validate and integrate:")
        print("  .venv/bin/python scripts/integrate_finetune.py")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("push")
    sub.add_parser("status")
    w = sub.add_parser("watch")
    w.add_argument("--interval", type=int, default=300, help="seconds between polls")
    f = sub.add_parser("fetch")
    f.add_argument("--into", default="/tmp/foodgenome-kaggle-output")
    args = p.parse_args()

    client = api()
    {"push": cmd_push, "status": cmd_status, "watch": cmd_watch, "fetch": cmd_fetch}[
        args.command
    ](client, args)


if __name__ == "__main__":
    main()
