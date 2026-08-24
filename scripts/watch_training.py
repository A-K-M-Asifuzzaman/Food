#!/usr/bin/env python
"""Live terminal dashboard for every long-running job in this project."""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import psutil
from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "artifacts" / "reports"
FEATURES = ROOT / "artifacts" / "features"
CHECKPOINTS = ROOT / "artifacts" / "checkpoints"

BACKBONES = ("siglip_so400m", "eva02_large", "dinov2_large")
SPLITS = ("train", "test")

SPARK = "▁▂▃▄▅▆▇█"

# tqdm writes "desc: 12%|███ | 165/9469 [04:15<3:49:55, 1.48s/batch, loss=0.9]".
TQDM = re.compile(
    r"(?P<desc>[^:]+):\s*(?P<pct>\d+)%\|[^|]*\|\s*(?P<cur>\d+)/(?P<total>\d+)\s*"
    r"\[(?P<elapsed>[\d:]+)<(?P<eta>[\d:?]+),\s*(?P<rate>[\d.]+)(?P<unit>s/batch|batch/s|it/s|s/it)"
    r"(?P<postfix>.*?)\]"
)
PROBE_EPOCH = re.compile(
    r"epoch\s+(?P<epoch>\d+)/(?P<total>\d+)\s+loss\s+(?P<loss>[\d.]+)\s+"
    r"val top1\s+(?P<top1>[\d.]+)\s+top5\s+(?P<top5>[\d.]+)"
)
FT_EPOCH = re.compile(
    r"\[(?P<stage>[^\]]+)\]\s+epoch\s+(?P<epoch>\d+)/(?P<total>\d+)\s+loss\s+(?P<loss>[\d.]+)\s+"
    r"val\s+(?P<val>[\d.]+)\s+ema\s+(?P<ema>[\d.]+)"
)

ACCENT = "#e62429"  # the red this project's UI is themed around
DIM = "grey50"


def human_secs(seconds: float) -> str:
    seconds = int(max(seconds, 0))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def sparkline(values: list[float], width: int = 32) -> str:
    """Render a value series as one line of block characters."""
    if not values:
        return ""
    vals = values[-width:]
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-9:
        return SPARK[len(SPARK) // 2] * len(vals)
    return "".join(SPARK[int((v - lo) / (hi - lo) * (len(SPARK) - 1))] for v in vals)


def bar(fraction: float, width: int = 20, filled: str = "█", empty: str = "░") -> str:
    fraction = min(max(fraction, 0.0), 1.0)
    n = int(round(fraction * width))
    return filled * n + empty * (width - n)


def tail_text(path: Path, nbytes: int = 8000) -> str:
    """Read the end of a log, treating carriage returns as line breaks."""
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - nbytes))
            raw = fh.read()
    except OSError:
        return ""
    return raw.decode("utf-8", "replace").replace("\r", "\n")


def last_match(text: str, pattern: re.Pattern) -> re.Match | None:
    found = None
    for m in pattern.finditer(text):
        found = m
    return found


@dataclass
class ExtractRow:
    backbone: str
    split: str
    state: str  # done | running | pending | failed
    pct: float = 0.0
    eta: str = "-"
    rate: str = "-"
    count: int = 0


def read_feature_bank() -> tuple[list[ExtractRow], float]:
    """Reconstruct extraction state from meta files plus the live log."""
    rows: list[ExtractRow] = []
    done_units = 0.0
    for key in BACKBONES:
        log = REPORTS / f"extract_{key}.log"
        text = tail_text(log) if log.exists() else ""
        failed = "exit=" in text and not re.search(r"exit=0", text)

        for split in SPLITS:
            meta_path = FEATURES / key / f"{split}_meta.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                except json.JSONDecodeError:
                    meta = {}
                rows.append(
                    ExtractRow(
                        key,
                        split,
                        "done",
                        1.0,
                        "-",
                        f"{meta.get('images_per_second', 0):.1f}",
                        int(meta.get("count", 0)),
                    )
                )
                done_units += 1
                continue

            m = last_match(text, TQDM)
            if m and m.group("desc").strip() == f"{key}/{split}":
                rate = float(m.group("rate"))
                unit = m.group("unit")
                # tqdm flips to s/batch once a batch takes over a second.
                ips = (8 / rate) if unit in {"s/batch", "s/it"} else rate * 8
                pct = int(m.group("pct")) / 100
                rows.append(
                    ExtractRow(key, split, "running", pct, m.group("eta"), f"{ips:.1f}", int(m.group("cur")))
                )
                done_units += pct
            else:
                rows.append(ExtractRow(key, split, "failed" if failed else "pending"))
    return rows, done_units / (len(BACKBONES) * len(SPLITS))


def feature_panel() -> Panel:
    rows, overall = read_feature_bank()
    table = Table.grid(padding=(0, 2))
    table.add_column("backbone", style="bold")
    table.add_column("split", style=DIM)
    table.add_column("progress")
    table.add_column("pct", justify="right")
    table.add_column("eta", justify="right")
    table.add_column("img/s", justify="right")

    styles = {
        "done": ("green", "done"),
        "running": (ACCENT, "running"),
        "pending": (DIM, "pending"),
        "failed": ("red bold", "FAILED"),
    }
    for r in rows:
        colour, _ = styles[r.state]
        if r.state == "done":
            prog = Text(bar(1.0), style="green")
            pct = Text("100%", style="green")
        elif r.state == "running":
            prog = Text(bar(r.pct), style=ACCENT)
            pct = Text(f"{r.pct * 100:.0f}%", style=ACCENT)
        else:
            prog = Text(bar(0.0), style=DIM)
            pct = Text("-", style=DIM)
        table.add_row(
            Text(r.backbone, style=colour),
            r.split,
            prog,
            pct,
            Text(r.eta, style=DIM),
            Text(r.rate, style=DIM),
        )

    header = Text.assemble(
        ("frozen feature bank  ", "bold"),
        (f"{overall * 100:.1f}% complete", ACCENT if overall < 1 else "green"),
    )
    return Panel(Group(header, Text(""), table), title="Stage 1 · feature extraction", border_style=DIM)


def find_active_training() -> tuple[str, Path] | None:
    """Most recently touched training log, if one is being written."""
    candidates: list[tuple[float, str, Path]] = []
    for path in REPORTS.glob("*.log"):
        if path.name.startswith("extract_"):
            continue
        candidates.append((path.stat().st_mtime, path.stem, path))
    if not candidates:
        return None
    mtime, name, path = max(candidates)
    if time.time() - mtime > 900:  # gone quiet for 15 min - treat as finished
        return None
    return name, path


def training_panel() -> Panel:
    active = find_active_training()
    histories = sorted(REPORTS.glob("*_history.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    probes = sorted(REPORTS.glob("probe_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    body: list = []

    if active:
        name, path = active
        text = tail_text(path)
        ft = last_match(text, FT_EPOCH)
        pr = last_match(text, PROBE_EPOCH)
        bar_m = last_match(text, TQDM)

        head = Table.grid(padding=(0, 3))
        head.add_column(style=DIM)
        head.add_column(style="bold")
        if ft:
            head.add_row("run", name)
            head.add_row("stage", ft.group("stage"))
            head.add_row("epoch", f"{ft.group('epoch')}/{ft.group('total')}")
            head.add_row("loss", ft.group("loss"))
            head.add_row("val top-1", Text(f"{ft.group('val')}%", style="green bold"))
            head.add_row("ema top-1", Text(f"{ft.group('ema')}%", style="green bold"))
        elif pr:
            head.add_row("run", name)
            head.add_row("epoch", f"{pr.group('epoch')}/{pr.group('total')}")
            head.add_row("loss", pr.group("loss"))
            head.add_row("val top-1", Text(f"{pr.group('top1')}%", style="green bold"))
            head.add_row("val top-5", Text(f"{pr.group('top5')}%", style="green"))
        else:
            head.add_row("run", name)
            head.add_row("status", "starting up")
        body.append(head)

        if bar_m:
            pct = int(bar_m.group("pct")) / 100
            post = bar_m.group("postfix").strip(" ,")
            body.append(Text(""))
            body.append(
                Text.assemble(
                    (bar(pct, 34), ACCENT),
                    (f"  {pct * 100:3.0f}%  ", "bold"),
                    (f"{bar_m.group('cur')}/{bar_m.group('total')}  ", DIM),
                    (f"eta {bar_m.group('eta')}  ", DIM),
                    (post, DIM),
                )
            )
    else:
        body.append(Text("no training process is currently writing a log", style=DIM))

    if histories:
        try:
            hist = json.loads(histories[0].read_text())
        except json.JSONDecodeError:
            hist = []
        if hist:
            vals = [h.get("val_top1", 0) for h in hist]
            emas = [h.get("ema_top1", 0) for h in hist]
            best = max(vals + emas)
            body.append(Text(""))
            body.append(
                Text.assemble(
                    (f"{histories[0].stem.replace('_history', '')}  ", "bold"),
                    (f"{len(hist)} epochs   best ", DIM),
                    (f"{best:.2f}%", "green bold"),
                )
            )
            body.append(Text.assemble(("val  ", DIM), (sparkline(vals), "green")))
            if any(emas):
                body.append(Text.assemble(("ema  ", DIM), (sparkline(emas), "cyan")))

    if probes:
        table = Table.grid(padding=(0, 2))
        table.add_column(style=DIM)
        table.add_column(justify="right", style="green bold")
        table.add_column(justify="right", style="green")
        shown = 0
        for p in probes:
            try:
                r = json.loads(p.read_text())
            except json.JSONDecodeError:
                continue
            table.add_row(r.get("name", p.stem), f"{r.get('test_top1', 0):.2f}", f"{r.get('test_top5', 0):.2f}")
            shown += 1
            if shown >= 6:
                break
        if shown:
            body.append(Text(""))
            body.append(Text("trained heads (test top-1 / top-5)", style="bold"))
            body.append(table)

    return Panel(Group(*body), title="Stage 2·3 · heads & fine-tune", border_style=DIM)


def system_panel() -> Panel:
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    disk = psutil.disk_usage(str(ROOT))
    gib = 1024**3

    swap_frac = sw.used / sw.total if sw.total else 0.0
    # Past 60% swap this machine started dropping the editor's tool channel.
    swap_style = "red bold" if swap_frac > 0.6 else "yellow" if swap_frac > 0.35 else "green"

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style=DIM, width=6)
    grid.add_column()
    grid.add_column(justify="right")
    grid.add_row("ram", Text(bar(vm.percent / 100, 24), style="cyan"), f"{vm.used / gib:.1f}/{vm.total / gib:.0f} GB")
    grid.add_row(
        "swap",
        Text(bar(swap_frac, 24), style=swap_style),
        Text(f"{sw.used / gib:.1f}/{sw.total / gib:.1f} GB", style=swap_style),
    )
    # A bare cpu_percent() reports 0.0 until it has a previous call to diff against, so
    # sample once over a short window and reuse the number.
    cpu = psutil.cpu_percent(interval=0.15)
    grid.add_row("cpu", Text(bar(cpu / 100, 24), style="magenta"), f"{cpu:.0f}%")
    grid.add_row("disk", Text(bar(disk.percent / 100, 24), style="blue"), f"{disk.free / gib:.0f} GB free")

    procs = []
    for p in psutil.process_iter(["name", "cmdline", "memory_info", "cpu_percent"]):
        try:
            cmd = " ".join(p.info["cmdline"] or [])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        # Both names are matched during the nutrivision -> foodgenome package rename;
        # the running extraction still uses the old module path.
        if "nutrivision" in cmd or "foodgenome" in cmd:
            stage = next((s for s in ("features", "probe", "finetune") if s in cmd), "python")
            procs.append((stage, p.info["memory_info"].rss / gib))
    if procs:
        # Dataloader workers share the parent's command line, so sort by resident size
        # to surface the process actually holding the model.
        procs.sort(key=lambda p: p[1], reverse=True)
        grid.add_row("", Text(""), "")
        for stage, rss in procs[:4]:
            grid.add_row("proc", Text(stage, style=ACCENT), f"{rss:.1f} GB rss")

    warn = None
    if swap_frac > 0.6:
        warn = Text(
            "  swap is high - this is what killed the first session. Close heavy apps.",
            style="red bold",
        )
    return Panel(Group(grid, *( [warn] if warn else [] )), title="System", border_style=DIM)


def log_panel(lines: int = 6) -> Panel:
    logs = sorted(REPORTS.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        return Panel(Text("no logs yet", style=DIM), title="Log", border_style=DIM)
    newest = logs[0]
    text = tail_text(newest, 4000)
    kept = [ln for ln in text.splitlines() if ln.strip()][-lines:]
    body = Text("\n".join(kept), style=DIM, overflow="ellipsis", no_wrap=True)
    return Panel(body, title=f"{newest.name}", border_style=DIM)


def header_panel(started: float) -> Panel:
    title = Text.assemble(
        ("FOOD", f"bold {ACCENT}"),
        ("GENOME", "bold white"),
        (" AI", f"bold {ACCENT}"),
        ("   live training", DIM),
    )
    meta = Text.assemble(
        (datetime.now().strftime("%H:%M:%S"), "bold"),
        ("   watching ", DIM),
        (human_secs(time.time() - started), "bold"),
    )
    grid = Table.grid(expand=True)
    grid.add_column(justify="left")
    grid.add_column(justify="right")
    grid.add_row(title, meta)
    return Panel(grid, border_style=ACCENT)


def render(started: float) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(header_panel(started), size=3),
        Layout(feature_panel(), size=12),
        Layout(training_panel(), name="train"),
        Layout(system_panel(), size=10),
        Layout(log_panel(), size=8),
    )
    return layout


def main() -> None:
    ap = argparse.ArgumentParser(description="Live dashboard for FoodGenome AI training jobs")
    ap.add_argument("--interval", type=float, default=2.0, help="refresh seconds")
    ap.add_argument("--once", action="store_true", help="render a single frame and exit")
    args = ap.parse_args()

    console = Console()
    started = time.time()

    if args.once:
        for panel in (
            header_panel(started),
            feature_panel(),
            training_panel(),
            system_panel(),
            log_panel(),
        ):
            console.print(panel)
        return

    try:
        with Live(render(started), console=console, refresh_per_second=4, screen=True) as live:
            while True:
                time.sleep(args.interval)
                live.update(render(started))
    except KeyboardInterrupt:
        console.print(Align.center(Text("watcher stopped - jobs keep running", style=DIM)))


if __name__ == "__main__":
    main()
