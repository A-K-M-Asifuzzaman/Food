# Running stage 3 on Kaggle — step by step

Fine-tuning EVA-02-L locally measured **124 hours**. On a Kaggle T4 the same schedule takes
roughly **7 hours** and fits inside a single session.

---

## The short answer: you upload nothing

This is the part worth stating plainly, because it is the opposite of what most Kaggle
guides assume.

| Thing | Upload it? | Why not |
|---|---|---|
| Food-101 images (6.1 GB) | **No** | Cell 3 downloads `ethz/food101` from Hugging Face directly into the session |
| EVA-02-L pretrained weights (1.2 GB) | **No** | `timm.create_model(pretrained=True)` fetches them |
| Your `nutrivision` package | **No** | The notebook is self-contained — every function it needs is copied in |
| Your feature bank (`artifacts/features/`, 619 MB) | **No** | Stage 3 fine-tunes from images, not from cached features |
| Your probe checkpoints | **No** | The fine-tune is independent of them; they get combined *afterwards*, locally |
| `eva02_large_448_last.pt` | **Only to resume** | See [§5](#5-if-it-does-not-finish-in-one-session) |

So for the first run: **upload nothing, just the notebook.**

---

## 1. Create the notebook

1. Go to <https://www.kaggle.com/code> → **New Notebook**
2. **File → Import Notebook** → upload `kaggle/foodgenome_finetune.ipynb` from this repo

Local path of the file to upload:

```
/Volumes/ssd(mac)2/Food/kaggle/foodgenome_finetune.ipynb
```

## 2. Settings (right-hand panel)

| Setting | Value | Why |
|---|---|---|
| **Accelerator** | `GPU T4 x2` (or `GPU P100`) | The notebook uses one GPU; T4 x2 just makes it easier to get a slot |
| **Internet** | `On` | Required — the dataset and pretrained weights are downloaded at runtime |
| **Persistence** | `Files only` | Keeps `/kaggle/working` between runs, so a re-run can resume |
| **Environment** | Latest | timm ≥ 1.0.11 is installed by cell 1 regardless |

> Without **Internet → On**, cell 3 fails immediately. It is the most common setup mistake.

## 3. Run it

**Run All.** Expected timings on a T4:

| Phase | Duration |
|---|---|
| Cell 1 — install timm/datasets | ~1 min |
| Cell 3 — download and export Food-101 | 10–15 min |
| Cell 4 — verify the split | seconds |
| Stage 1 — 6 epochs at 224px | ~2.5 h |
| Stage 2 — 3 epochs at 448px | ~4.5 h |
| Cell 8 — test evaluation and logit export | ~10 min |

**Cell 4 is the gate.** It asserts the validation split matches the local one:

```
mask sha256 : a1e99550d007a01ab5654f2125816155307ba1b27d7329cd23cf4a3bcfa170d7
split verified - matches the local run
```

If that assertion fails, stop. A different validation slice means the fine-tune cannot be
compared against the 97.156% frozen ensemble, and combining them would leak validation data
into the final number.

## 4. Paths inside the session

Everything the notebook writes goes to `/kaggle/working`, which becomes the notebook's
Output:

```
/kaggle/working/
├── food101/                          ← downloaded dataset (not saved to Output)
│   ├── train/apple_pie/apple_pie_000000.jpg …
│   ├── test/apple_pie/apple_pie_000012.jpg …
│   └── meta.json
├── eva02_large_448_last.pt           ← resumable checkpoint, written every epoch
├── eva02_ft_result.json              ← final test top-1/top-5 and per-epoch history
└── logits/
    ├── probe_eva02_ft_val.npy        ← 3,030 × 101
    ├── probe_eva02_ft_test.npy       ← 25,250 × 101
    ├── val_y.npy
    └── test_y.npy
```

The checkpoint is ~1.2 GB, so it lands comfortably inside Kaggle's 20 GB Output limit.

## 5. If it does not finish in one session

Kaggle caps GPU sessions at 12 h; the notebook stops itself at 11 h (`cfg.max_hours`) and
checkpoints rather than losing an epoch to the wall.

1. **Save Version** → *Save & Run All*, and let it commit
2. Open the finished version → **Output** tab → **New Dataset**, name it e.g.
   `foodgenome-ckpt`
3. Back in the notebook: **Add Input** → *Datasets* → attach `foodgenome-ckpt`
4. **Run All** again

Cell 7 searches `/kaggle/input/**/eva02_large_448_last.pt` and resumes from the exact epoch
it stopped at — no config change needed.

## 6. Bringing the results home

From the notebook's **Output** tab, download and place locally:

| Download from Kaggle | Put it here locally |
|---|---|
| `eva02_large_448_last.pt` | `/Volumes/ssd(mac)2/Food/artifacts/checkpoints/` |
| `logits/probe_eva02_ft_val.npy` | `/Volumes/ssd(mac)2/Food/artifacts/reports/logits/` |
| `logits/probe_eva02_ft_test.npy` | `/Volumes/ssd(mac)2/Food/artifacts/reports/logits/` |
| `eva02_ft_result.json` | `/Volumes/ssd(mac)2/Food/artifacts/reports/` |

You do **not** need to copy `val_y.npy` or `test_y.npy` — the local repo already has them,
and cell 4's checksum is what guarantees they describe the same split.

## 7. Then, locally — no training required

The exported logits use the same `.npy` layout as the frozen probes, so the fine-tune drops
straight into the existing evaluation:

```bash
cd "/Volumes/ssd(mac)2/Food"

# Does the fine-tune actually beat the frozen pair, or merely differ from it?
.venv/bin/python -m nutrivision.training.ensemble \
    --members siglip_so400m eva02_large eva02_ft

# Re-fit conformal sets over whichever combination wins
.venv/bin/python -m nutrivision.reliability.conformal \
    --members siglip_so400m eva02_ft
```

`ensemble.py` sweeps every subset in probability and logit space and pairs each headline
number with an exact McNemar test — so it will tell you whether any gain over **97.156%** is
real or inside the noise. Both scripts run in seconds against cached logits.

## 8. Tuning if you hit trouble

| Symptom | Fix |
|---|---|
| CUDA OOM in stage 2 | `cfg.stage2_bs = 8`, `cfg.grad_accum = 3` — effective batch is `bs × grad_accum`, and only the product affects the result |
| CUDA OOM in stage 1 | `cfg.stage1_bs = 16`, `cfg.grad_accum = 4` |
| Too slow to finish | `cfg.stage1_epochs = 3` — stage 1 is the cheap phase, but 448px is where EVA-02's advantage lives, so cut stage 1 before stage 2 |
| Want it faster, accept less | `cfg.grad_checkpointing = False` — roughly 20% faster, but needs more memory |

## 9. What this does not change

The Food-101 test split stays sealed until cell 8. Validation is the same fixed 4%
stratified slice, seed 1337. Every hyperparameter matches the local configuration, so the
Kaggle result is directly comparable to the numbers already recorded in `prompt.md` — that
comparability is the whole point of the checksum in cell 4.
