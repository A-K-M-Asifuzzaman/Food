from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class LinearProbe(nn.Module):
    def __init__(self, dim: int, num_classes: int):
        super().__init__()
        self.norm = nn.LayerNorm(dim)
        self.fc = nn.Linear(dim, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(self.norm(x))


class MLPProbe(nn.Module):
    def __init__(self, dim: int, num_classes: int, hidden: int = 1536, dropout: float = 0.3):
        super().__init__()
        self.net = nn.Sequential(
            nn.LayerNorm(dim),
            nn.Linear(dim, hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.LayerNorm(hidden),
            nn.Linear(hidden, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class GatedFusionProbe(nn.Module):

    def __init__(
        self,
        dims: list[int],
        num_classes: int,
        proj: int = 1024,
        hidden: int = 1536,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.projections = nn.ModuleList(
            nn.Sequential(nn.LayerNorm(d), nn.Linear(d, proj), nn.GELU()) for d in dims
        )
        self.gate = nn.Sequential(
            nn.Linear(proj * len(dims), len(dims)),
            nn.Softmax(dim=-1),
        )
        self.head = nn.Sequential(
            nn.LayerNorm(proj),
            nn.Linear(proj, hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.LayerNorm(hidden),
            nn.Linear(hidden, num_classes),
        )
        self.dims = dims

    def forward(self, xs: list[torch.Tensor], return_gate: bool = False):
        projected = [p(x) for p, x in zip(self.projections, xs, strict=True)]
        stacked = torch.stack(projected, dim=1)
        weights = self.gate(torch.cat(projected, dim=-1)).unsqueeze(-1)
        fused = (stacked * weights).sum(dim=1)
        logits = self.head(fused)
        if return_gate:
            return logits, weights.squeeze(-1)
        return logits


def soft_target_cross_entropy(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    return torch.sum(-targets * F.log_softmax(logits, dim=-1), dim=-1).mean()


def mixup_features(
    x: torch.Tensor, y: torch.Tensor, num_classes: int, alpha: float, smoothing: float
) -> tuple[torch.Tensor, torch.Tensor]:
    off = smoothing / num_classes
    on = 1.0 - smoothing + off
    targets = torch.full((y.size(0), num_classes), off, device=y.device)
    targets.scatter_(1, y.unsqueeze(1), on)

    if alpha <= 0:
        return x, targets

    lam = float(torch.distributions.Beta(alpha, alpha).sample())
    perm = torch.randperm(x.size(0), device=x.device)
    return lam * x + (1 - lam) * x[perm], lam * targets + (1 - lam) * targets[perm]
