"""Stream the Quick, Draw! simplified NDJSON files and keep a region-balanced
sample of each category (without ever storing the multi-GB raw files).

For every category we reservoir-sample up to MAX_PER_REGION recognized
drawings per region and save their strokes compactly to data/<category>.npz.

Run:  python -m doodle.download
"""
import json
import random
import sys
import urllib.parse
import urllib.request
from multiprocessing import Pool

import numpy as np

from .config import CATEGORIES, DATA_DIR, MAX_PER_REGION, SEED
from .regions import NUM_REGIONS, REGION_NAMES, region_of

URL = "https://storage.googleapis.com/quickdraw_dataset/full/simplified/{}.ndjson"


def fetch_category(word):
    out = DATA_DIR / f"{word.replace(' ', '_')}.npz"
    if out.exists():
        return word, None
    rng = random.Random(f"{SEED}-{word}")
    kept = [[] for _ in range(NUM_REGIONS)]     # reservoir per region
    seen = [0] * NUM_REGIONS
    url = URL.format(urllib.parse.quote(word))
    with urllib.request.urlopen(url, timeout=120) as resp:
        for line in resp:
            rec = json.loads(line)
            if not rec["recognized"]:
                continue
            region = region_of(rec["countrycode"])
            if region is None:
                continue
            seen[region] += 1
            item = (rec["countrycode"], rec["drawing"])
            if len(kept[region]) < MAX_PER_REGION:
                kept[region].append(item)
            else:
                j = rng.randrange(seen[region])
                if j < MAX_PER_REGION:
                    kept[region][j] = item

    xy, stroke_len, n_strokes, regions, countries = [], [], [], [], []
    for region, items in enumerate(kept):
        for country, drawing in items:
            n_strokes.append(len(drawing))
            regions.append(region)
            countries.append(country)
            for xs, ys in drawing:
                stroke_len.append(len(xs))
                xy.append(np.stack([xs, ys], axis=1).astype(np.uint8))
    np.savez_compressed(
        out,
        xy=np.concatenate(xy),                         # all points, (P, 2) uint8 in 0..255
        stroke_len=np.asarray(stroke_len, np.uint16),  # points per stroke
        n_strokes=np.asarray(n_strokes, np.uint16),    # strokes per drawing
        region=np.asarray(regions, np.uint8),
        country=np.asarray(countries),
        seen=np.asarray(seen),                         # how many existed per region
    )
    return word, seen


def main():
    DATA_DIR.mkdir(exist_ok=True)
    with Pool(5) as pool:
        for word, seen in pool.imap_unordered(fetch_category, CATEGORIES):
            if seen is None:
                print(f"{word}: already downloaded")
            else:
                counts = ", ".join(f"{n.split()[0][:6]} {s}" for n, s in zip(REGION_NAMES, seen))
                print(f"{word}: available per region -> {counts}")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
