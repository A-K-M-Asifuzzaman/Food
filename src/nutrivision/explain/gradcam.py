"""Grad-CAM over the frozen-backbone probe, for Vision Transformers.

Grad-CAM was written for convolutional networks, where the last conv feature map
is already a spatial grid and channel-mean gradients are a sensible importance
weight. A ViT needs two adjustments, and getting either wrong produces a map
that looks plausible and means nothing.

**Where to tap.** The gradient is taken at the output of the final transformer
block, whose tokens still carry position. Tapping after pooling would give a
single vector with no spatial extent; tapping too early gives tokens that have
not yet been mixed into anything class-relevant.

**What the classifier actually is.** The probe does not see the image — it sees a
pooled, L2-normalised feature vector. So the gradient has to flow from the probe
logit, back through the normalisation and the pooling head, into the tokens. Any
shortcut that scores tokens directly against the classifier weights would be
explaining a model that is not the one making the prediction.

SigLIP-SO400M pools with a learned attention head (MAP) and carries no prefix
token, so all 729 tokens are spatial and none needs stripping. The code reads
`num_prefix_tokens` rather than assuming, because EVA-02 does carry a CLS token
and including it would fold a non-spatial vector into the grid.

**Which method, measured rather than assumed.** Three were implemented and
compared on 24 test images by how much attribution mass lands in the outer ring,
which covers 60% of the frame. Food-101 subjects are usually centred, so less
border mass means better localisation:

| method | border mass | vs chance |
|---|---|---|
| `gradcam` — channel-mean weights | 52.4% | **0.87x** |
| `tokencam` — per-position act x grad | 60.2% | 1.00x |
| `attention_pool_map` — MAP head weights | 68.6% | 1.14x |

Grad-CAM wins, and is also the more class-discriminative: swapping the target
class from pizza to churros changes its map almost completely (r = +0.07)
against r = +0.38 for token-CAM.

The attention map losing is the interesting result. Reading the pooling head's
weights should be the most faithful account of what the model looked at, but it
is *worse than chance* at finding the subject — which independently reproduces
the known artefact where ViTs park high-attention "register" tokens in
low-information background patches. Attention is not saliency here.

Localisation is weak in absolute terms for all three, and the honest reason is
architectural: the probe never sees the image, only a globally pooled vector, so
spatial attribution has to be recovered through a pooling step that deliberately
discarded position.
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from nutrivision.config import DEVICE, NUM_CLASSES


class GradCAM:
    """Class-discriminative spatial attribution for one backbone + probe pair."""

    def __init__(self, backbone, probe, layer=None, mode="gradcam", norm_quantile=0.97):
        self.backbone = backbone
        self.probe = probe
        self.mode = mode
        self.norm_quantile = norm_quantile
        self.layer = layer if layer is not None else backbone.blocks[-1]
        self._activations: torch.Tensor | None = None
        self._gradients: torch.Tensor | None = None
        self._handles = []

    def __enter__(self):
        def forward_hook(_module, _inputs, output):
            # retain_grad is what makes the backward hook unnecessary and keeps
            # this working under autocast, where hook-captured grads can arrive
            # in a different dtype than the activation.
            self._activations = output
            output.retain_grad()

        self._handles.append(self.layer.register_forward_hook(forward_hook))
        return self

    def __exit__(self, *exc):
        for h in self._handles:
            h.remove()
        self._handles.clear()

    def __call__(
        self, tensor: torch.Tensor, class_index: int | None = None
    ) -> tuple[np.ndarray, int, float]:
        """Return (heatmap in [0,1] on the patch grid, class index, logit)."""
        self.backbone.zero_grad(set_to_none=True)
        self.probe.zero_grad(set_to_none=True)

        features = self.backbone(tensor)
        logits = self.probe(F.normalize(features.float(), dim=-1))
        index = int(logits.argmax(dim=-1)) if class_index is None else class_index
        score = logits[0, index]
        score.backward()

        activations = self._activations
        gradients = activations.grad
        if gradients is None:
            raise RuntimeError("no gradient reached the tapped layer")

        prefix = getattr(self.backbone, "num_prefix_tokens", 0)
        act = activations[0, prefix:].detach().float()
        grad = gradients[0, prefix:].detach().float()

        if self.mode == "gradcam":
            # Classic Grad-CAM: one importance weight per channel, averaged over
            # positions. The channel-mean is a convolutional heuristic and on a
            # ViT it discards where in the image each channel's gradient came
            # from, which is most of the signal.
            weights = grad.mean(dim=0)
            cam = F.relu((act * weights).sum(dim=-1))
        else:
            # Per-position first-order contribution of each token to the class
            # score. Keeps the gradient's spatial structure instead of averaging
            # it away, which is what makes it the better fit for transformers.
            cam = F.relu((act * grad).sum(dim=-1))

        grid = self.backbone.patch_embed.grid_size
        cam = cam.reshape(grid[0], grid[1])
        cam = cam - cam.min()

        # Normalise against a high percentile, not the maximum. Attribution maps
        # here are heavily skewed - typically 70% of patches are exactly zero
        # after the rectification - so a single outlier patch scales everything
        # else towards invisibility and the map reads as empty.
        flat = cam.flatten()
        scale = float(torch.quantile(flat, self.norm_quantile))
        if scale <= 0:
            scale = float(flat.max())
        if scale > 0:
            cam = (cam / scale).clamp(0, 1)
        return cam.cpu().numpy(), index, float(score.detach())


@torch.no_grad()
def attention_pool_map(backbone, tensor: torch.Tensor) -> np.ndarray | None:
    """Attention weights of the pooling head over the patch grid.

    For a MAP-pooled ViT this is the most faithful "where did it look" available:
    a single learned latent query attends over every patch, and those weights are
    literally the mixture that becomes the feature vector the probe classifies.
    Gradient methods have to work backwards through that pooling; this reads it
    directly.

    The trade-off is honest and worth stating: attention is *not* class
    discriminative. It shows where the representation came from, not which class
    that evidence supported, so it complements Grad-CAM rather than replacing it.

    timm dispatches to a fused attention kernel that never materialises the
    weight matrix, so it is recomputed here from the module's own projections
    rather than by hooking - the arithmetic is identical to the fused path.
    """
    pool = getattr(backbone, "attn_pool", None)
    if pool is None:
        return None

    tokens = backbone.forward_features(tensor)
    prefix = getattr(backbone, "num_prefix_tokens", 0)
    if prefix:
        tokens = tokens[:, prefix:]

    x = tokens
    if getattr(pool, "pos_embed", None) is not None:
        x = x + pool.pos_embed.unsqueeze(0).to(x.dtype)

    b, n, _ = x.shape
    heads, dim = pool.num_heads, pool.head_dim

    q = pool.q(pool.latent.expand(b, -1, -1))
    q = q.reshape(b, pool.latent_len, heads, dim).transpose(1, 2)
    k = pool.kv(x).reshape(b, n, 2, heads, dim).permute(2, 0, 3, 1, 4)[0]
    q, k = pool.q_norm(q), pool.k_norm(k)

    attn = (q * pool.scale) @ k.transpose(-2, -1)
    weights = attn.softmax(dim=-1)[0].mean(dim=0).mean(dim=0)  # heads, then latents

    grid = backbone.patch_embed.grid_size
    cam = weights.reshape(grid[0], grid[1]).float()
    cam = cam - cam.min()
    scale = float(torch.quantile(cam.flatten(), 0.97)) or float(cam.max())
    if scale > 0:
        cam = (cam / scale).clamp(0, 1)
    return cam.cpu().numpy()


def overlay(image: Image.Image, cam: np.ndarray, alpha: float = 0.78, gamma: float = 1.8) -> Image.Image:
    """Composite a heatmap onto the image using the project's ink/red ramp.

    A perceptually ordered ramp matters here: the classic jet colormap is not
    monotonic in lightness, so it invents structure that the data does not have
    and readers reliably misjudge which region scored highest.
    """
    size = image.size
    heat = Image.fromarray((cam * 255).astype(np.uint8), mode="L").resize(
        size, Image.BICUBIC
    )
    h = np.asarray(heat).astype(np.float32) / 255.0
    # Gamma above 1 suppresses the mid range. Percentile normalisation already
    # rescued the map from invisibility; without this it over-corrects and half
    # the frame reads as evidence. Tuning it further would only be dressing up
    # an attribution that measures as weakly localised — see the module note.
    h = h ** gamma

    base = np.asarray(image.convert("RGB")).astype(np.float32)
    # newsprint -> comic red, lightness increasing with attribution
    cold = np.array([11, 11, 15], dtype=np.float32)
    hot = np.array([230, 36, 41], dtype=np.float32)
    ramp = cold + (hot - cold) * h[..., None]

    mixed = base * (1 - alpha * h[..., None]) + ramp * (alpha * h[..., None])
    return Image.fromarray(np.clip(mixed, 0, 255).astype(np.uint8))


def explain(
    image: Image.Image,
    backbone,
    transform,
    probe,
    class_index: int | None = None,
    mode: str = "gradcam",
) -> dict:
    tensor = transform(image).unsqueeze(0).to(DEVICE)
    tensor.requires_grad_(False)
    with GradCAM(backbone, probe, mode=mode) as cam_fn:
        cam, index, score = cam_fn(tensor, class_index)

    assert 0 <= index < NUM_CLASSES
    return {
        "cam": cam,
        "class_index": index,
        "logit": score,
        "grid": list(cam.shape),
        # How concentrated the evidence is. A map spread evenly over the whole
        # frame is not an explanation, and this is the number that says so.
        "peak_fraction": float((cam > 0.5).mean()),
    }
