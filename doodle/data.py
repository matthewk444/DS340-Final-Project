"""Dataset: loads the sampled strokes and renders images on the fly, so the
same drawing can be shown complete or partially finished."""
import numpy as np
import torch
from torch.utils.data import Dataset

from .config import CATEGORIES, DATA_DIR, SEED
from .render import render, truncate


class Strokes:
    """All drawings of all categories in a few flat arrays."""

    def __init__(self):
        xy, stroke_len, n_strokes, region, category = [], [], [], [], []
        for ci, word in enumerate(CATEGORIES):
            z = np.load(DATA_DIR / f"{word.replace(' ', '_')}.npz")
            xy.append(z["xy"])
            stroke_len.append(z["stroke_len"])
            n_strokes.append(z["n_strokes"])
            region.append(z["region"])
            category.append(np.full(len(z["region"]), ci, np.uint8))
        self.xy = np.concatenate(xy)
        stroke_len = np.concatenate(stroke_len).astype(np.int64)
        n_strokes = np.concatenate(n_strokes).astype(np.int64)
        self.region = np.concatenate(region).astype(np.int64)
        self.category = np.concatenate(category).astype(np.int64)
        self.point_start = np.concatenate([[0], np.cumsum(stroke_len)])   # per stroke
        self.stroke_start = np.concatenate([[0], np.cumsum(n_strokes)])   # per drawing

    def __len__(self):
        return len(self.region)

    def get(self, i):
        a, b = self.stroke_start[i], self.stroke_start[i + 1]
        return [self.xy[self.point_start[s]:self.point_start[s + 1]] for s in range(a, b)]


def split_indices(n, seed=SEED):
    """80 / 10 / 10 train / val / test split (fixed by the seed)."""
    perm = np.random.default_rng(seed).permutation(n)
    a, b = int(0.8 * n), int(0.9 * n)
    return perm[:a], perm[a:b], perm[b:]


class DoodleDataset(Dataset):
    """mode:
      'complete' - always the finished drawing
      'mixed'    - half finished drawings, half cut off at a random 15-100%
      a float    - always cut off at that fraction (for evaluation)
    """

    def __init__(self, strokes, indices, mode="complete"):
        self.s, self.idx, self.mode = strokes, np.asarray(indices), mode

    def __len__(self):
        return len(self.idx)

    def __getitem__(self, k):
        i = int(self.idx[k])
        drawing = self.s.get(i)
        if self.mode == "mixed":
            if np.random.rand() < 0.5:
                drawing = truncate(drawing, np.random.uniform(0.15, 1.0))
        elif self.mode != "complete":
            drawing = truncate(drawing, float(self.mode))
        img = torch.from_numpy(render(drawing))
        return img, int(self.s.category[i]), int(self.s.region[i])
