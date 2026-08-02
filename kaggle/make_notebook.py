"""Emit the Kaggle fine-tuning notebook. Written as a generator so the cell
source stays readable Python instead of hand-escaped JSON."""

import json
import pathlib

MASK_SHA = "a1e99550d007a01ab5654f2125816155307ba1b27d7329cd23cf4a3bcfa170d7"

cells = []


def md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").split("\n")})


def code(text):
    cells.append(
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": text.strip("\n").split("\n"),
        }
    )


md(r"""
# FoodGenome AI — EVA-02-L fine-tune on Kaggle

Stage 3 of the FoodGenome AI project. Fine-tunes `eva02_large_patch14_448` on Food-101
with a progressive 224 → 448 schedule, layer-wise learning-rate decay, mixup/cutmix and an
EMA shadow model.

**Why this notebook exists.** The same run on an 18 GB M3 Pro measured 5.8 h per epoch at
224 and 29.4 h per epoch at 448 — about 124 h for the full schedule. A single T4 does it in
roughly 7 h, which fits inside one Kaggle session.

**The one thing that must not drift.** Validation is a fixed 4% class-stratified slice
carved out of *train*, seed 1337. The test split is never touched until final evaluation.
Cell 4 reproduces that split and verifies it against a SHA-256 computed on the local
machine — if it does not match, stop, because every accuracy number downstream becomes
incomparable and the ensemble would leak.

**Session budget.** Kaggle GPU sessions cap at 12 h. The loop checkpoints after every epoch
and stops gracefully before the wall, so a run can span sessions. See the last cell.

Set **Settings → Accelerator → GPU T4 x2** (or P100) and **Internet → On**.
""")

md("## 1. Environment")

code(r"""
import subprocess, sys, torch

print("torch", torch.__version__, "| cuda", torch.cuda.is_available())
for i in range(torch.cuda.device_count()):
    p = torch.cuda.get_device_properties(i)
    print(f"  gpu{i}: {p.name}  {p.total_memory/2**30:.1f} GB")

# timm 1.x is required: this uses set_grad_checkpointing, ModelEmaV3 and
# param_groups_layer_decay, none of which exist in the 0.x line Kaggle may pin.
subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "timm>=1.0.11", "datasets>=2.19"], check=True)

import timm
print("timm", timm.__version__)

# Optional. Anonymous downloads work but are rate-limited, which is felt when
# pulling 6 GB of Food-101 plus the pretrained weights. To enable: Add-ons ->
# Secrets -> add HF_TOKEN (get one at huggingface.co/settings/tokens, Read scope).
import os
try:
    from kaggle_secrets import UserSecretsClient
    os.environ["HF_TOKEN"] = UserSecretsClient().get_secret("HF_TOKEN")
    print("HF_TOKEN loaded from Kaggle Secrets")
except Exception:
    print("No HF_TOKEN secret found - continuing anonymously (slower, rate-limited)")
""")

md("## 2. Configuration\n\nEvery value here matches the local run so results stay comparable.")

code(r"""
from dataclasses import dataclass, field

@dataclass
class Config:
    backbone: str = "eva02_large_patch14_448.mim_m38m_ft_in22k_in1k"
    num_classes: int = 101
    seed: int = 1337
    val_fraction: float = 0.04

    # Progressive resize. Stage 1 does the bulk of the learning cheaply at 224;
    # stage 2 adapts to the resolution the checkpoint was actually trained for.
    #
    # Epoch counts are sized to finish inside one 12 h Kaggle session, measured
    # on T4 x2: 52 min per epoch at 224, 3 h 32 m at 448. The original 6+3 costs
    # 16 h and cannot complete. 4+2 costs about 11 h including the download and
    # the final evaluation.
    #
    # Stage 1 was already flattening when it was cut - 91.39, 92.18, 92.31 over
    # its last three epochs - so the epochs given up there are the cheapest in
    # the schedule, and stage 2 has the resolution advantage to recover them.
    stage1_size: int = 224
    stage1_epochs: int = 4
    stage1_bs: int = 32
    stage1_lr: float = 1e-4

    stage2_size: int = 448
    stage2_epochs: int = 2
    stage2_bs: int = 12
    stage2_lr: float = 2e-5

    grad_accum: int = 2
    weight_decay: float = 0.05
    layer_decay: float = 0.75
    warmup_epochs: float = 0.5
    label_smoothing: float = 0.1
    mixup_alpha: float = 0.8
    cutmix_alpha: float = 1.0
    mix_prob: float = 0.5
    drop_path: float = 0.2
    ema_decay: float = 0.9998
    workers: int = 4

    # A stage-2 epoch runs about 3.5 h. Checkpointing only at epoch boundaries
    # means a disconnect can cost all of it, which is exactly what happened at
    # 83% of one. Snapshot weights periodically instead: a resume replays the
    # current epoch from its start but keeps the learning, so the worst case
    # drops from one whole epoch to one interval.
    save_every_batches: int = 300

    # Kaggle's T4 x2 gives two 14.6 GB cards. DataParallel splits each batch
    # across them, so per-GPU memory matches the single-card tuning while
    # throughput roughly doubles. Batch sizes below are per GPU and are scaled
    # by the device count at run time.
    data_parallel: bool = True
    grad_checkpointing: bool = True   # needed for 448 on a 14.6 GB card
    # Kaggle kills the session at 12 h. Stop early and checkpoint instead of
    # losing an epoch to the wall. 11.5 leaves room for the final evaluation
    # after the last epoch lands at roughly 10.8 h.
    max_hours: float = 11.5

cfg = Config()
DATA = "/kaggle/working/food101"
OUT  = "/kaggle/working"
print(cfg)
""")

md(r"""
## 3. Data

Downloads `ethz/food101` and writes it as an image-folder tree using **exactly** the naming
the local pipeline used — `{class}_{global_row_index:06d}.jpg`. That naming is what makes
the validation split reproducible, because the split is defined over files sorted by name
within each class.

Takes about 10-15 minutes. If you attach Food-101 as a Kaggle dataset instead, the file
ordering will differ and cell 4's checksum will fail — use this path.
""")

code(r"""
import json, os
from pathlib import Path
from datasets import load_dataset
from tqdm.auto import tqdm

def export(split_name: str, out_split: str):
    root = Path(DATA) / out_split
    if (root / ".done").exists():
        print(f"{out_split}: already exported")
        return
    ds = load_dataset("ethz/food101", split=split_name)
    labels = ds.features["label"].names
    for name in labels:
        (root / name).mkdir(parents=True, exist_ok=True)
    # enumerate order == HF row order, which is what the local export used
    for idx, row in enumerate(tqdm(ds, desc=f"export {out_split}")):
        name = labels[row["label"]]
        img = row["image"]
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(root / name / f"{name}_{idx:06d}.jpg", "JPEG", quality=95, optimize=True)
    (root / ".done").touch()
    Path(DATA, "meta.json").write_text(json.dumps({"classes": labels}))

export("train", "train")
export("validation", "test")   # HF calls Food-101's official test split "validation"

CLASSES = sorted(p.name for p in Path(DATA, "train").iterdir() if p.is_dir())
print(len(CLASSES), "classes:", CLASSES[:3], "...", CLASSES[-2:])
""")

md(r"""
## 4. The split — verify before training

`holdout_mask` is copied verbatim from `src/nutrivision/data/dataset.py`. The single shared
RNG matters: it is drawn sequentially across the class loop, so the result depends on class
order as well as seed.

**If the SHA does not match, stop.** Continuing would train against a different validation
slice than the local probes were calibrated on, which silently invalidates every comparison
and leaks validation data into the ensemble.
""")

code(rf"""
import hashlib
import numpy as np

LOCAL_MASK_SHA = "{MASK_SHA}"

def holdout_mask(targets, num_classes, val_fraction, seed=1337):
    rng = np.random.default_rng(seed)
    is_val = np.zeros(len(targets), dtype=bool)
    for label in range(num_classes):
        idx = np.flatnonzero(targets == label)
        rng.shuffle(idx)
        n_val = max(1, int(round(len(idx) * val_fraction)))
        is_val[idx[:n_val]] = True
    return is_val

# Items grouped by class in sorted order, files sorted within each class —
# identical to how Food101Folder builds its list locally.
train_items, train_labels = [], []
for label, cls in enumerate(CLASSES):
    for p in sorted((Path(DATA, "train") / cls).glob("*.jpg")):
        train_items.append(p)
        train_labels.append(label)
train_labels = np.array(train_labels)

is_val = holdout_mask(train_labels, cfg.num_classes, cfg.val_fraction, cfg.seed)
sha = hashlib.sha256(is_val.tobytes()).hexdigest()

print(f"train items {{len(train_items)}}  val {{int(is_val.sum())}}  train {{int((~is_val).sum())}}")
print("mask sha256 :", sha)
print("expected    :", LOCAL_MASK_SHA)
assert len(train_items) == 75750, "unexpected train size"
assert sha == LOCAL_MASK_SHA, "SPLIT MISMATCH - do not train, results would be incomparable"
print("\nsplit verified - matches the local run")
""")

md("## 5. Datasets and transforms")

code(r"""
import timm, torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from timm.data import create_transform

class FoodSubset(Dataset):
    def __init__(self, paths, labels, transform):
        self.paths, self.labels, self.transform = paths, labels, transform
    def __len__(self):
        return len(self.paths)
    def __getitem__(self, i):
        img = Image.open(self.paths[i]).convert("RGB")
        return self.transform(img), int(self.labels[i])

test_items, test_labels = [], []
for label, cls in enumerate(CLASSES):
    for p in sorted((Path(DATA, "test") / cls).glob("*.jpg")):
        test_items.append(p); test_labels.append(label)
test_labels = np.array(test_labels)
print("test items", len(test_items))

MEAN, STD = timm.data.IMAGENET_DEFAULT_MEAN, timm.data.IMAGENET_DEFAULT_STD

def loaders(size, bs):
    train_tf = create_transform(
        input_size=(3, size, size), is_training=True,
        auto_augment="rand-m9-mstd0.5-inc1", interpolation="bicubic",
        re_prob=0.25, re_mode="pixel", re_count=1, mean=MEAN, std=STD,
    )
    eval_tf = create_transform(
        input_size=(3, size, size), is_training=False,
        interpolation="bicubic", crop_pct=1.0, mean=MEAN, std=STD,
    )
    tr = FoodSubset([p for p, v in zip(train_items, is_val) if not v],
                    train_labels[~is_val], train_tf)
    va = FoodSubset([p for p, v in zip(train_items, is_val) if v],
                    train_labels[is_val], eval_tf)
    kw = dict(num_workers=cfg.workers, pin_memory=True, persistent_workers=cfg.workers > 0)
    return (DataLoader(tr, batch_size=bs, shuffle=True, drop_last=True, **kw),
            DataLoader(va, batch_size=bs * 2, shuffle=False, **kw))

def test_loader(size, bs):
    eval_tf = create_transform(
        input_size=(3, size, size), is_training=False,
        interpolation="bicubic", crop_pct=1.0, mean=MEAN, std=STD,
    )
    return DataLoader(FoodSubset(test_items, test_labels, eval_tf),
                      batch_size=bs * 2, shuffle=False, num_workers=cfg.workers, pin_memory=True)
""")

md(r"""
## 6. Model

The published checkpoint is a fixed-448 model whose patch embed asserts on any other input
size, so a 224 stage cannot run against it directly. Each stage is therefore built at its own
`img_size` and the position embedding is resampled once at the transition — rather than
interpolated on every forward pass, which puts an antialiased resize inside the autograd
graph for no benefit.
""")

code(r"""
import torch.nn as nn
from timm.layers import resample_abs_pos_embed
from timm.utils import ModelEmaV3

DEVICE = torch.device("cuda")

def resize_state_dict(sd, model):
    out = dict(sd)
    if "pos_embed" in out and out["pos_embed"].shape != model.pos_embed.shape:
        out["pos_embed"] = resample_abs_pos_embed(
            out["pos_embed"].float(),
            new_size=list(model.patch_embed.grid_size),
            num_prefix_tokens=model.num_prefix_tokens,
            verbose=False,
        )
    return out

def build_model(size, weights=None):
    m = timm.create_model(
        cfg.backbone, pretrained=weights is None,
        num_classes=cfg.num_classes, drop_path_rate=cfg.drop_path, img_size=size,
    )
    if weights is not None:
        m.load_state_dict(resize_state_dict(weights, m))
    m = m.to(DEVICE)
    if cfg.grad_checkpointing:
        m.set_grad_checkpointing(True)
    return m

def param_groups(model, lr):
    from timm.optim import param_groups_layer_decay
    return param_groups_layer_decay(
        model, weight_decay=cfg.weight_decay, layer_decay=cfg.layer_decay,
    )

N_GPU = torch.cuda.device_count() if cfg.data_parallel else 1

# Wrap for the forward pass only. The raw module stays the one the optimiser,
# the EMA and every state_dict touch, so checkpoints never pick up
# DataParallel's 'module.' key prefix and stay loadable on a single-GPU machine.
def parallelise(module):
    return nn.DataParallel(module) if N_GPU > 1 else module

print(f"using {N_GPU} GPU(s)")
""")

md("## 7. Training")

code(r"""
import math, time
from timm.data import Mixup
from timm.loss import SoftTargetCrossEntropy
from tqdm.auto import tqdm

CKPT = Path(OUT) / "eva02_large_448_last.pt"
PARTIAL = Path(OUT) / "eva02_large_448_partial.pt"

def find_resume():
    # Prefer whichever is further along. A mid-epoch snapshot of the epoch after
    # the last completed one carries strictly more training than that boundary.
    def rank(p):
        try:
            s = torch.load(p, map_location="cpu", weights_only=False)
        except Exception:
            return None
        stage_i = 1 if s.get("stage") == "stage2" else 0
        return (stage_i, s.get("epoch", 0), s.get("batches_done", 10**9)), p

    found = [r for r in (rank(p) for p in [CKPT, PARTIAL] if p.exists()) if r]
    for root in [Path("/kaggle/input")]:
        for name in ("eva02_large_448_last.pt", "eva02_large_448_partial.pt"):
            for p in root.rglob(name):
                r = rank(p)
                if r:
                    found.append(r)
    if not found:
        return None
    return max(found, key=lambda r: r[0])[1]

@torch.no_grad()
def evaluate(model, loader, desc="val"):
    model.eval()
    top1 = top5 = n = 0
    for x, y in tqdm(loader, desc=desc, unit="batch", leave=False):
        x, y = x.to(DEVICE, non_blocking=True), y.to(DEVICE, non_blocking=True)
        with torch.autocast("cuda", dtype=torch.float16):
            out = model(x)
        _, pred = out.topk(5, dim=-1)
        correct = pred.eq(y[:, None])
        top1 += correct[:, 0].sum().item()
        top5 += correct.any(dim=1).sum().item()
        n += y.numel()
    return top1 / n, top5 / n

def run_stage(model, ema, name, size, bs_per_gpu, epochs, lr, state, deadline):
    bs = bs_per_gpu * N_GPU
    runner = parallelise(model)
    ema_runner = parallelise(ema.module)
    train_loader, val_loader = loaders(size, bs)
    mixup = Mixup(mixup_alpha=cfg.mixup_alpha, cutmix_alpha=cfg.cutmix_alpha,
                  prob=cfg.mix_prob, switch_prob=0.5, mode="batch",
                  label_smoothing=cfg.label_smoothing, num_classes=cfg.num_classes)
    criterion = SoftTargetCrossEntropy()
    opt = torch.optim.AdamW(param_groups(model, lr), lr=lr, betas=(0.9, 0.999))
    scaler = torch.amp.GradScaler("cuda")

    steps_per_epoch = math.ceil(len(train_loader) / cfg.grad_accum)
    total = steps_per_epoch * epochs
    warmup = max(1, int(cfg.warmup_epochs * steps_per_epoch))

    def lr_scale(step):
        if step < warmup:
            return step / warmup
        p = (step - warmup) / max(1, total - warmup)
        return 0.5 * (1 + math.cos(math.pi * p))

    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_scale)
    start = state.get("epoch", 0) if state.get("stage") == name else 0
    for _ in range(start * steps_per_epoch):
        sched.step()

    history = state.get("history", [])
    for epoch in range(start, epochs):
        model.train()
        t0, running, seen, micro = time.time(), 0.0, 0, 0
        # tqdm.auto renders a real progress bar in the notebook, so the elapsed
        # and remaining time for the epoch are visible rather than inferred.
        pbar = tqdm(train_loader, desc=f"{name} e{epoch+1}/{epochs}", unit="batch")
        for x, y in pbar:
            x, y = x.to(DEVICE, non_blocking=True), y.to(DEVICE, non_blocking=True)
            x, target = mixup(x, y)
            with torch.autocast("cuda", dtype=torch.float16):
                loss = criterion(runner(x), target) / cfg.grad_accum
            scaler.scale(loss).backward()
            micro += 1
            if micro % cfg.grad_accum == 0:
                scaler.unscale_(opt)
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(opt); scaler.update()
                opt.zero_grad(set_to_none=True)
                sched.step(); ema.update(model)
            running += loss.item() * cfg.grad_accum
            seen += 1
            if seen % 20 == 0:
                pbar.set_postfix(loss=f"{running/seen:.3f}",
                                 ips=f"{seen*bs/(time.time()-t0):.1f}")

            # Mid-epoch snapshot. Written to a separate file so a crash during
            # the write cannot corrupt the last good epoch-boundary checkpoint.
            if cfg.save_every_batches and seen % cfg.save_every_batches == 0:
                torch.save({"stage": name, "epoch": epoch, "partial": True,
                            "batches_done": seen, "history": history,
                            "best_acc": state.get("best_acc", 0.0),
                            "model": {k: v.cpu() for k, v in model.state_dict().items()},
                            "ema": {k: v.cpu() for k, v in ema.module.state_dict().items()}},
                           PARTIAL)
                pbar.write(f"  snapshot at batch {seen} -> {PARTIAL.name}")

        acc1, acc5 = evaluate(runner, val_loader, "val")
        ema1, ema5 = evaluate(ema_runner, val_loader, "val ema")
        best = max(acc1, ema1)
        mins = (time.time() - t0) / 60
        print(f"\n[{name}] epoch {epoch+1}/{epochs}  val {acc1*100:.2f}  "
              f"ema {ema1*100:.2f}  ({mins:.1f} min)")

        history.append({"stage": name, "epoch": epoch + 1, "size": size,
                        "val_top1": round(acc1 * 100, 3), "ema_top1": round(ema1 * 100, 3),
                        "minutes": round(mins, 2)})
        state = {"stage": name, "epoch": epoch + 1, "history": history,
                 "best_acc": max(state.get("best_acc", 0.0), best),
                 "model": {k: v.cpu() for k, v in model.state_dict().items()},
                 "ema": {k: v.cpu() for k, v in ema.module.state_dict().items()}}
        torch.save(state, CKPT)
        print(f"  checkpointed -> {CKPT}")

        if time.time() > deadline:
            print("\nApproaching the session limit. Checkpoint saved; "
                  "resume in a new session (see the last cell).")
            return state, True
    return state, False
""")

code(r"""
deadline = time.time() + cfg.max_hours * 3600

resume = find_resume()
state = {}
if resume:
    state = torch.load(resume, map_location="cpu", weights_only=False)
    print(f"resuming from {resume}: stage={state.get('stage')} epoch={state.get('epoch')}")

weights, ema_weights = state.get("model"), state.get("ema")
stages = [("stage1", cfg.stage1_size, cfg.stage1_epochs, cfg.stage1_bs, cfg.stage1_lr),
          ("stage2", cfg.stage2_size, cfg.stage2_epochs, cfg.stage2_bs, cfg.stage2_lr)]

stopped = False
for name, size, epochs, bs_per_gpu, lr in stages:
    if stopped or epochs <= 0:
        continue
    if state.get("stage") == "stage2" and name == "stage1":
        continue
    if state.get("stage") == name and state.get("epoch", 0) >= epochs:
        continue

    model = build_model(size, weights)
    ema = ModelEmaV3(model, decay=cfg.ema_decay, device=DEVICE)
    if ema_weights is not None:
        ema.module.load_state_dict(resize_state_dict(ema_weights, model))
    print(f"{name}: {size}px  bs={bs_per_gpu}x{N_GPU}={bs_per_gpu*N_GPU}  "
          f"{sum(p.numel() for p in model.parameters())/1e6:.1f}M params")

    state, stopped = run_stage(model, ema, name, size, bs_per_gpu, epochs, lr, state, deadline)
    weights = {k: v.cpu() for k, v in model.state_dict().items()}
    ema_weights = {k: v.cpu() for k, v in ema.module.state_dict().items()}
    del model, ema
    torch.cuda.empty_cache()

print("\nbest validation top-1:", round(state.get("best_acc", 0) * 100, 3))
""")

md(r"""
## 8. Final evaluation and logit export

Exports validation and test logits in the same `.npy` layout the local repo uses, so the
fine-tuned model drops straight into `nutrivision.training.ensemble` and
`nutrivision.reliability.conformal` alongside the frozen probes.

**This is the first and only time the test split is used.**
""")

code(r"""
if not stopped:
    model = build_model(cfg.stage2_size if cfg.stage2_epochs else cfg.stage1_size, weights)
    ema = ModelEmaV3(model, decay=cfg.ema_decay, device=DEVICE)
    ema.module.load_state_dict(resize_state_dict(ema_weights, model))

    size = cfg.stage2_size if cfg.stage2_epochs else cfg.stage1_size
    bs = cfg.stage2_bs * N_GPU
    _, val_loader = loaders(size, bs)
    te_loader = test_loader(size, bs)

    # Pick the weights that won on validation; never on test.
    raw_runner, ema_runner = parallelise(model), parallelise(ema.module)
    use_ema = evaluate(ema_runner, val_loader, "val ema")[0] > \
              evaluate(raw_runner, val_loader, "val raw")[0]
    final = ema_runner if use_ema else raw_runner
    print("using", "EMA" if use_ema else "raw", "weights")

    @torch.no_grad()
    def logits_for(loader, desc):
        final.eval()
        out = []
        for x, _ in tqdm(loader, desc=desc, unit="batch"):
            with torch.autocast("cuda", dtype=torch.float16):
                out.append(final(x.to(DEVICE)).float().cpu())
        return torch.cat(out).numpy()

    val_logits = logits_for(val_loader, "val logits")
    test_logits = logits_for(te_loader, "test logits")
    d = Path(OUT) / "logits"; d.mkdir(exist_ok=True)
    np.save(d / "probe_eva02_ft_val.npy", val_logits.astype("float32"))
    np.save(d / "probe_eva02_ft_test.npy", test_logits.astype("float32"))
    np.save(d / "val_y.npy", train_labels[is_val])
    np.save(d / "test_y.npy", test_labels)

    acc1 = (test_logits.argmax(1) == test_labels).mean()
    top5 = (np.argsort(-test_logits, 1)[:, :5] == test_labels[:, None]).any(1).mean()
    print(f"\nTEST top-1 {acc1*100:.3f}   top-5 {top5*100:.3f}")
    print("local frozen ensemble was 97.156 - this is the number to beat")

    json.dump({"test_top1": round(float(acc1) * 100, 3),
               "test_top5": round(float(top5) * 100, 3),
               "history": state.get("history", [])},
              open(Path(OUT) / "eva02_ft_result.json", "w"), indent=2)
else:
    print("Training did not finish this session - skipping test evaluation.")
""")

md(r"""
## 9. Continuing across sessions

Kaggle caps a GPU session at 12 h and this schedule needs roughly 7 h on a T4, so it should
finish in one. If it stops early:

1. **Save version** → wait for the run to commit. `eva02_large_448_last.pt` lands in the
   notebook's Output.
2. Create a **Dataset from the notebook output** (Output tab → *New Dataset*).
3. Attach that dataset to the notebook and re-run. Cell 7 finds
   `eva02_large_448_last.pt` anywhere under `/kaggle/input` and resumes from the exact
   epoch it stopped at.

**Bringing the result home**

Download from the notebook Output:

- `eva02_large_448_last.pt` → `artifacts/checkpoints/`
- `logits/probe_eva02_ft_{val,test}.npy` → `artifacts/reports/logits/`
- `eva02_ft_result.json` → `artifacts/reports/`

Then the fine-tune joins the existing evaluation without any new training:

```bash
.venv/bin/python -m nutrivision.training.ensemble \
    --members siglip_so400m eva02_large eva02_ft
.venv/bin/python -m nutrivision.reliability.conformal \
    --members siglip_so400m eva02_ft
```

The ensemble script sweeps every subset and runs exact McNemar tests, so it will say whether
the fine-tune actually beats the 97.156% frozen pair or merely differs from it.

**If you hit OOM**, lower `stage2_bs` to 8 and raise `grad_accum` to 3 — the effective batch
is `bs × grad_accum` and only that product affects the result.
""")

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
        "accelerator": "GPU",
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = pathlib.Path("/Volumes/ssd(mac)2/Food/kaggle/foodgenome_finetune.ipynb")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(nb, indent=1))
print("wrote", out, len(cells), "cells")
