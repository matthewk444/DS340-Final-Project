"""Rasterize Natural Earth country polygons into a low-res "pixel art" world
grid where each cell stores a region id. The game draws this grid on a canvas
and makes each region glow with the model's confidence.

Usage:  python scripts/build_world_map.py path/to/ne_50m_admin_0_countries.geojson
Source: https://github.com/nvkelso/natural-earth-vector (public domain)
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from doodle.regions import REGION_KEYS, REGION_NAMES, region_of  # noqa: E402

W, H = 128, 60                 # grid size (cells)
LAT_TOP, LAT_BOTTOM = 80.0, -56.0
SS = 4                         # supersampling factor


def main(path):
    geo = json.load(open(path))
    big = Image.new("L", (W * SS, H * SS), 0)   # 0 = ocean, r+1 = region r
    draw = ImageDraw.Draw(big)

    def project(lon, lat):
        x = (lon + 180.0) / 360.0 * W * SS
        y = (LAT_TOP - lat) / (LAT_TOP - LAT_BOTTOM) * H * SS
        return x, y

    for feat in geo["features"]:
        props = feat["properties"]
        code = props.get("ISO_A2_EH")
        if code in (None, "-99"):
            code = props.get("ISO_A2")
        region = region_of(code)
        if region is None:
            # fall back on the continent for anything unmapped
            fallback = {"Africa": "mideast_africa", "Oceania": "oceania",
                        "South America": "latin_america"}.get(props.get("CONTINENT"))
            if fallback is None:
                continue
            region = REGION_KEYS.index(fallback)
        geom = feat["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            ring = [project(lon, lat) for lon, lat in poly[0]]
            if len(ring) < 3:
                continue
            fill = region
            # overseas territories (e.g. French Guiana) belong to where they are, not to Europe
            mean_lon = sum(lon for lon, _ in poly[0]) / len(poly[0])
            if REGION_KEYS[region] == "western_europe" and mean_lon < -30:
                fill = REGION_KEYS.index("latin_america")
            draw.polygon(ring, fill=fill + 1)

    # downsample: a cell is land if >= 35% of its subpixels are land;
    # its region is the most common region among them
    px = big.load()
    grid = []
    for gy in range(H):
        row = []
        for gx in range(W):
            counts = {}
            for sy in range(SS):
                for sx in range(SS):
                    v = px[gx * SS + sx, gy * SS + sy]
                    counts[v] = counts.get(v, 0) + 1
            land = {k: v for k, v in counts.items() if k != 0}
            if land and sum(land.values()) >= 0.35 * SS * SS:
                row.append(max(land, key=land.get))
            else:
                row.append(0)
        grid.append(row)

    out = {
        "width": W, "height": H,
        "regions": [{"key": k, "name": n} for k, n in zip(REGION_KEYS, REGION_NAMES)],
        # one string per row; '.' = ocean, digit = region id
        "rows": ["".join("." if v == 0 else str(v - 1) for v in row) for row in grid],
    }
    dest = Path(__file__).resolve().parents[1] / "web" / "assets" / "worldmap.json"
    dest.write_text(json.dumps(out))
    print("wrote", dest)
    for r in out["rows"]:
        print(r)


if __name__ == "__main__":
    main(sys.argv[1])
