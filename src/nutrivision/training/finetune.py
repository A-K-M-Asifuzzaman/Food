from __future__ import annotations

import argparse
import gc
import json
import math
import signal
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import timm
import torch
import torch.nn as nn
from timm.data import Mixup, create_transform, resolve_data_config
from timm.layers import resample_abs_pos_embed
from timm.loss import SoftTargetCrossEntropy
from timm.utils import ModelEmaV3
from torch.utils.data import DataLoader
from tqdm import tqdm

from nutrivision.config import (
    CHECKPOINT_DIR,
    DEVICE,
    NUM_CLASSES,
    REPORT_DIR,
    SEED,
    FinetuneConfig,
)
from nutrivision.data.dataset import Food101Folder

_INTERRUPTED = False


def _on_signal(signum, frame):
    global _INTERRUPTED
    _INTERRUPTED = True
    print("\ninterrupt received, finishing this step then checkpointing")


signal.signal(signal.SIGINT, _on_signal)
signal.signal(signal.SIGTERM, _on_signal)


def autocast_ctx(enabled: bool = True):
    if DEVICE.type == "cpu" or not enabled:
        return torch.autocast("cpu", enabled=False)
    dtype = torch.bfloat16 if DEVICE.type == "mps" else torch.float16
    return torch.autocast(device_type=DEVICE.type, dtype=dtype)


def build_loaders(cfg: FinetuneConfig, image_size: int):
    model_cfg = {
        "input_size": (3, image_size, image_size),
        "mean": timm.data.IMAGENET_DEFAULT_MEAN,
        "std": timm.data.IMAGENET_DEFAULT_STD,
        "crop_pct": 1.0,
        "interpolation": "bicubic",
    }
    train_tf = create_transform(
        **model_cfg,
        is_training=True,
        auto_augment="rand-m9-mstd0.5-inc1",
        re_prob=0.25,
        re_mode="pixel",
        re_count=1,
        scale=(0.5, 1.0),
        ratio=(3 / 4, 4 / 3),
        hflip=0.5,
        color_jitter=0.3,
    )
    eval_tf = create_transform(**{**model_cfg, "crop_pct": 0.95}, is_training=False)

    train_ds = Food101Folder("train", transform=train_tf, val_fraction=cfg.val_fraction)
    val_ds = Food101Folder("val", transform=eval_tf, val_fraction=cfg.val_fraction)

    common = dict(
        num_workers=cfg.num_workers,
        pin_memory=DEVICE.type == "cuda",
        persistent_workers=cfg.num_workers > 0,
        prefetch_factor=4 if cfg.num_workers > 0 else None,
    )
    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=True, drop_last=True, **common)
    val_loader = DataLoader(val_ds, batch_size=max(1, cfg.batch_size), shuffle=False, **common)
    return train_loader, val_loader


def layerwise_param_groups(model, base_lr: float, weight_decay: float, layer_decay: float):
    try:
        from timm.optim import param_groups_layer_decay

        return param_groups_layer_decay(
            model, weight_decay=weight_decay, layer_decay=layer_decay, no_weight_decay_list=model.no_weight_decay()
        )
    except Exception:
        decay, no_decay = [], []
        for name, p in model.named_parameters():
            if not p.requires_grad:
                continue
            if p.ndim == 1 or name.endswith(".bias"):
                no_decay.append(p)
            else:
                decay.append(p)
        return [
            {"params": decay, "weight_decay": weight_decay},
            {"params": no_decay, "weight_decay": 0.0},
        ]


@torch.no_grad()
def validate(model, loader, device=DEVICE) -> tuple[float, float]:
    model.eval()
    correct1 = correct5 = total = 0
    for images, target in tqdm(loader, desc="val", leave=False, unit="batch"):
        images = images.to(device, non_blocking=True)
        target = target.to(device, non_blocking=True)
        with autocast_ctx():
            logits = model(images)
        top5 = logits.float().topk(5, dim=-1).indices
        correct1 += (top5[:, 0] == target).sum().item()
        correct5 += (top5 == target.unsqueeze(1)).any(dim=1).sum().item()
        total += target.size(0)
    return correct1 / total, correct5 / total


def run_stage(
    model,
    ema,
    cfg: FinetuneConfig,
    image_size: int,
    epochs: int,
    lr: float,
    stage_name: str,
    state: dict,
) -> dict:
    train_loader, val_loader = build_loaders(cfg, image_size)
    mixup = Mixup(
        mixup_alpha=cfg.mixup_alpha,
        cutmix_alpha=cfg.cutmix_alpha,
        prob=cfg.mix_prob,
        switch_prob=0.5,
        mode="batch",
        label_smoothing=cfg.label_smoothing,
        num_classes=NUM_CLASSES,
    )
    criterion = SoftTargetCrossEntropy()

    groups = layerwise_param_groups(model, lr, cfg.weight_decay, cfg.layer_decay)
    opt = torch.optim.AdamW(groups, lr=lr, betas=(0.9, 0.999))

    steps_per_epoch = math.ceil(len(train_loader) / cfg.grad_accum)
    total = steps_per_epoch * epochs
    warmup = max(1, int(cfg.warmup_epochs * steps_per_epoch))

    def lr_scale(step: int) -> float:
        if step < warmup:
            return (step + 1) / warmup
        p = (step - warmup) / max(1, total - warmup)
        return 0.5 * (1 + math.cos(math.pi * p)) * (1 - 0.01) + 0.01

    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_scale)

    start_epoch = 0
    if state.get("stage") == stage_name and state.get("optimizer"):
        opt.load_state_dict(state["optimizer"])
        sched.load_state_dict(state["scheduler"])
        start_epoch = state["epoch"] + 1
        print(f"resuming {stage_name} at epoch {start_epoch + 1}")

    ckpt_path = CHECKPOINT_DIR / f"{cfg.out_name}_last.pt"
    best_path = CHECKPOINT_DIR / f"{cfg.out_name}_best.pt"
    best_acc = state.get("best_acc", 0.0)
    history = state.get("history", [])

    for epoch in range(start_epoch, epochs):
        model.train()
        opt.zero_grad(set_to_none=True)
        running, seen, t0 = 0.0, 0, time.time()
        micro = 0

        pbar = tqdm(train_loader, desc=f"{stage_name} e{epoch + 1}/{epochs}", unit="batch")
        for images, target in pbar:
            images = images.to(DEVICE, non_blocking=True)
            target = target.to(DEVICE, non_blocking=True)
            images, soft_target = mixup(images, target)

            with autocast_ctx():
                loss = criterion(model(images), soft_target) / cfg.grad_accum
            loss.backward()
            micro += 1

            if micro % cfg.grad_accum == 0:
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                opt.zero_grad(set_to_none=True)
                sched.step()
                ema.update(model)

            running += loss.item() * cfg.grad_accum
            seen += 1
            if seen % cfg.log_every == 0:
                rate = seen * cfg.batch_size / (time.time() - t0)
                pbar.set_postfix(loss=f"{running / seen:.3f}", ips=f"{rate:.1f}")

            if _INTERRUPTED:
                break

        acc1, acc5 = validate(model, val_loader)
        ema_acc1, ema_acc5 = validate(ema.module, val_loader)
        use_ema = ema_acc1 > acc1
        report_acc = max(acc1, ema_acc1)

        history.append(
            {
                "stage": stage_name,
                "epoch": epoch + 1,
                "image_size": image_size,
                "loss": round(running / max(seen, 1), 4),
                "val_top1": round(acc1 * 100, 3),
                "val_top5": round(acc5 * 100, 3),
                "ema_top1": round(ema_acc1 * 100, 3),
                "ema_top5": round(ema_acc5 * 100, 3),
                "minutes": round((time.time() - t0) / 60, 2),
            }
        )
        print(
            f"[{stage_name}] epoch {epoch + 1}/{epochs}  loss {running / max(seen, 1):.4f}  "
            f"val {acc1 * 100:.2f}  ema {ema_acc1 * 100:.2f}  ({(time.time() - t0) / 60:.1f} min)"
        )

        state = {
            "stage": stage_name,
            "epoch": epoch,
            "model": model.state_dict(),
            "ema": ema.module.state_dict(),
            "optimizer": opt.state_dict(),
            "scheduler": sched.state_dict(),
            "best_acc": max(best_acc, report_acc),
            "history": history,
            "config": asdict(cfg),
            "image_size": image_size,
        }
        torch.save(state, ckpt_path)
        (REPORT_DIR / f"{cfg.out_name}_history.json").write_text(json.dumps(history, indent=2))

        if report_acc > best_acc:
            best_acc = report_acc
            torch.save(
                {
                    "model": (ema.module if use_ema else model).state_dict(),
                    "ema_selected": use_ema,
                    "val_top1": report_acc,
                    "image_size": image_size,
                    "backbone": cfg.backbone,
                    "config": asdict(cfg),
                },
                best_path,
            )

        if _INTERRUPTED:
            print(f"checkpointed to {ckpt_path}, exiting")
            raise SystemExit(0)

    state["best_acc"] = best_acc
    return state


def resize_state_dict(sd: dict, model) -> dict:
    out = {k: v for k, v in sd.items()}
    key = "pos_embed"
    if key in out and out[key].shape != model.pos_embed.shape:
        out[key] = resample_abs_pos_embed(
            out[key].float(),
            new_size=list(model.patch_embed.grid_size),
            num_prefix_tokens=model.num_prefix_tokens,
            verbose=False,
        )
    return out


def build_model(cfg: FinetuneConfig, size: int, weights: dict | None, grad_ckpt: bool):
    model = timm.create_model(
        cfg.backbone,
        pretrained=weights is None,
        num_classes=NUM_CLASSES,
        drop_path_rate=cfg.drop_path,
        img_size=size,
    )
    if weights is not None:
        model.load_state_dict(resize_state_dict(weights, model))
    model = model.to(DEVICE)
    if grad_ckpt:
        model.set_grad_checkpointing(True)
    return model


def main() -> None:
    p = argparse.ArgumentParser(description="Fine-tune a backbone on Food-101")
    p.add_argument("--backbone", default=FinetuneConfig.backbone)
    p.add_argument("--out-name", default=FinetuneConfig.out_name)
    p.add_argument("--stage1-size", type=int, default=224)
    p.add_argument("--stage1-epochs", type=int, default=6)
    p.add_argument("--stage1-bs", type=int, default=16)
    p.add_argument("--stage2-size", type=int, default=448)
    p.add_argument("--stage2-epochs", type=int, default=3)
    p.add_argument("--stage2-bs", type=int, default=4)
    p.add_argument("--no-grad-checkpointing", action="store_true")
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--stage2-lr", type=float, default=2e-5)
    p.add_argument("--grad-accum", type=int, default=4)
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--layer-decay", type=float, default=0.75)
    p.add_argument("--drop-path", type=float, default=0.2)
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()

    torch.manual_seed(SEED)
    np.random.seed(SEED)

    cfg = FinetuneConfig(
        backbone=args.backbone,
        out_name=args.out_name,
        grad_accum=args.grad_accum,
        num_workers=args.workers,
        layer_decay=args.layer_decay,
        drop_path=args.drop_path,
    )

    state: dict = {}
    ckpt_path = CHECKPOINT_DIR / f"{cfg.out_name}_last.pt"
    if args.resume and ckpt_path.exists():
        state = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        print(f"loaded checkpoint from {ckpt_path} (stage={state.get('stage')}, epoch={state.get('epoch')})")

    stages = [
        ("stage1", args.stage1_size, args.stage1_epochs, args.stage1_bs, args.lr),
        ("stage2", args.stage2_size, args.stage2_epochs, args.stage2_bs, args.stage2_lr),
    ]
    done = state.get("stage")
    weights = state.get("model")
    ema_weights = state.get("ema")

    for name, size, epochs, bs, lr in stages:
        if epochs <= 0:
            continue
        if done == "stage2" and name == "stage1":
            continue

        model = build_model(cfg, size, weights, not args.no_grad_checkpointing)
        ema = ModelEmaV3(model, decay=cfg.ema_decay, device=DEVICE)
        if ema_weights is not None:
            ema.module.load_state_dict(resize_state_dict(ema_weights, model))
        params = sum(p.numel() for p in model.parameters()) / 1e6
        print(f"{cfg.backbone}  {params:.1f}M params  {size}px  bs={bs}  device={DEVICE}")

        cfg.batch_size = bs
        cfg.image_size = size
        carried = state if state.get("stage") == name else {
            "best_acc": state.get("best_acc", 0.0),
            "history": state.get("history", []),
        }
        state = run_stage(model, ema, cfg, size, epochs, lr, name, carried)

        weights = {k: v.detach().cpu() for k, v in model.state_dict().items()}
        ema_weights = {k: v.detach().cpu() for k, v in ema.module.state_dict().items()}
        del model, ema
        gc.collect()
        if DEVICE.type == "mps":
            torch.mps.empty_cache()

    print(f"best validation top-1: {state.get('best_acc', 0) * 100:.2f}")


if __name__ == "__main__":
    main()
