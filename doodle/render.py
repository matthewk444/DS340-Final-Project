"""Turn stroke data into the 3-channel image the CNN sees.

A plain black-and-white bitmap throws away *how* something was drawn, which
is exactly the kind of habit that differs between regions (e.g. which way
people draw a circle). So we render three channels:

  0. ink            - the drawing itself
  1. drawing order  - ink brightness ramps from dim (first ink) to bright (latest ink)
  2. stroke direction - within every stroke, brightness ramps from start to end

Channels 1 and 2 use arc length (not point count), so the dataset's simplified
strokes and the dense strokes from the live whiteboard look the same.
The same function is used for training and for the live game.
"""
import numpy as np
from PIL import Image, ImageDraw

from .config import IMG_SIZE

PAD = 5          # empty border, in pixels
LINE_WIDTH = 2
RAMP_MIN = 0.25  # dimmest ramp value, so early ink is still visible


def truncate(strokes, fraction):
    """Keep only the first `fraction` (by ink length) of a drawing."""
    if fraction >= 1.0:
        return strokes
    lengths = [np.hypot(*np.diff(s.astype(np.float32), axis=0).T).sum() + 1e-3 for s in strokes]
    budget = fraction * sum(lengths)
    out = []
    for s, length in zip(strokes, lengths):
        if budget <= 0:
            break
        if length <= budget:
            out.append(s)
        else:
            n = max(2, int(round(len(s) * budget / length)))
            out.append(s[:n])
        budget -= length
    return out or [strokes[0][:2]]


def render(strokes, size=IMG_SIZE):
    """strokes: list of (n, 2) arrays of x, y points in any coordinate system.
    Returns a float32 array (3, size, size) with values in 0..1."""
    strokes = [np.asarray(s, np.float32).reshape(-1, 2) for s in strokes]
    strokes = [s for s in strokes if len(s) > 0]
    canvases = [Image.new("L", (size, size), 0) for _ in range(3)]
    if not strokes:
        return np.zeros((3, size, size), np.float32)

    # fit the bounding box of what has been drawn so far into the image
    pts = np.concatenate(strokes)
    lo, hi = pts.min(0), pts.max(0)
    span = max(float((hi - lo).max()), 1e-3)
    scale = (size - 1 - 2 * PAD) / span
    offset = (size - 1 - (hi - lo) * scale) / 2.0
    strokes = [(s - lo) * scale + offset for s in strokes]

    seg_len = [np.hypot(*np.diff(s, axis=0).T) if len(s) > 1 else np.zeros(0, np.float32)
               for s in strokes]
    total = sum(float(l.sum()) for l in seg_len) + 1e-6
    draws = [ImageDraw.Draw(c) for c in canvases]
    done = 0.0
    for s, lens in zip(strokes, seg_len):
        if len(s) == 1:  # a dot
            x, y = s[0]
            v = int(255 * (RAMP_MIN + (1 - RAMP_MIN) * done / total))
            box = [x - 1, y - 1, x + 1, y + 1]
            draws[0].ellipse(box, fill=255)
            draws[1].ellipse(box, fill=v)
            draws[2].ellipse(box, fill=255)
            continue
        draws[0].line([tuple(p) for p in s], fill=255, width=LINE_WIDTH)
        stroke_total = float(lens.sum()) + 1e-6
        along = 0.0
        for i in range(len(s) - 1):
            mid = along + lens[i] / 2.0
            seg = [tuple(s[i]), tuple(s[i + 1])]
            order = RAMP_MIN + (1 - RAMP_MIN) * (done + mid) / total
            direction = RAMP_MIN + (1 - RAMP_MIN) * mid / stroke_total
            draws[1].line(seg, fill=int(255 * order), width=LINE_WIDTH)
            draws[2].line(seg, fill=int(255 * direction), width=LINE_WIDTH)
            along += float(lens[i])
        done += stroke_total
    return np.stack([np.asarray(c, np.float32) / 255.0 for c in canvases])
