from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from nutrivision.config import DEVICE, NUM_CLASSES


class GradCAM:

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
            weights = grad.mean(dim=0)
            cam = F.relu((act * weights).sum(dim=-1))
        else:
            cam = F.relu((act * grad).sum(dim=-1))

        grid = self.backbone.patch_embed.grid_size
        cam = cam.reshape(grid[0], grid[1])
        cam = cam - cam.min()

        flat = cam.flatten()
        scale = float(torch.quantile(flat, self.norm_quantile))
        if scale <= 0:
            scale = float(flat.max())
        if scale > 0:
            cam = (cam / scale).clamp(0, 1)
        return cam.cpu().numpy(), index, float(score.detach())


@torch.no_grad()
def attention_pool_map(backbone, tensor: torch.Tensor) -> np.ndarray | None:
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
    weights = attn.softmax(dim=-1)[0].mean(dim=0).mean(dim=0)

    grid = backbone.patch_embed.grid_size
    cam = weights.reshape(grid[0], grid[1]).float()
    cam = cam - cam.min()
    scale = float(torch.quantile(cam.flatten(), 0.97)) or float(cam.max())
    if scale > 0:
        cam = (cam / scale).clamp(0, 1)
    return cam.cpu().numpy()


def overlay(image: Image.Image, cam: np.ndarray, alpha: float = 0.78, gamma: float = 1.8) -> Image.Image:
    size = image.size
    heat = Image.fromarray((cam * 255).astype(np.uint8), mode="L").resize(
        size, Image.BICUBIC
    )
    h = np.asarray(heat).astype(np.float32) / 255.0
    h = h ** gamma

    base = np.asarray(image.convert("RGB")).astype(np.float32)
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
        "peak_fraction": float((cam > 0.5).mean()),
    }
