"""Cut Natural Earth's 10 m land polygons down to the Bay of Bengal for the offline map.

    curl -L -o data/raw/naturalearth/ne_10m_land.geojson \
      https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_land.geojson
    python -I tools/make_land.py data/raw/naturalearth/ne_10m_land.geojson

Writes data/geo/land.geojson (public domain data from naturalearthdata.com).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import GEO_DIR  # noqa: E402

BBOX = (77.0, 3.0, 99.0, 18.0)  # lon min, lat min, lon max, lat max: Chennai to northern Sumatra
MIN_STEP_DEG = 0.01  # drop vertices closer than ~1 km to the previous one


def clip_ring(ring, bbox):
    """Sutherland-Hodgman: clip a closed ring to an axis-aligned box."""
    x0, y0, x1, y1 = bbox
    edges = [
        (lambda p: p[0] >= x0, lambda a, b: (x0, a[1] + (b[1] - a[1]) * (x0 - a[0]) / (b[0] - a[0]))),
        (lambda p: p[0] <= x1, lambda a, b: (x1, a[1] + (b[1] - a[1]) * (x1 - a[0]) / (b[0] - a[0]))),
        (lambda p: p[1] >= y0, lambda a, b: (a[0] + (b[0] - a[0]) * (y0 - a[1]) / (b[1] - a[1]), y0)),
        (lambda p: p[1] <= y1, lambda a, b: (a[0] + (b[0] - a[0]) * (y1 - a[1]) / (b[1] - a[1]), y1)),
    ]
    pts = [tuple(p[:2]) for p in ring]
    for inside, cross in edges:
        if not pts:
            break
        out = []
        prev = pts[-1]
        for cur in pts:
            if inside(cur):
                if not inside(prev):
                    out.append(cross(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cross(prev, cur))
            prev = cur
        pts = out
    return pts


def thin(pts):
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) >= MIN_STEP_DEG:
            out.append(p)
    return out


def main(src: str) -> None:
    features = json.loads(Path(src).read_text(encoding="utf-8"))["features"]
    polygons = []
    for f in features:
        geom = f["geometry"]
        parts = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in parts:
            outer = thin(clip_ring(poly[0], BBOX))
            if len(outer) >= 4:
                ring = [[round(x, 3), round(y, 3)] for x, y in outer]
                polygons.append([ring + [ring[0]]])
    out = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"source": "Natural Earth 10m land v5.1.2 (public domain)", "bbox": BBOX},
            "geometry": {"type": "MultiPolygon", "coordinates": polygons},
        }],
    }
    dest = GEO_DIR / "land.geojson"
    dest.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"{dest}: {len(polygons)} polygons, {dest.stat().st_size / 1000:.0f} kB")


if __name__ == "__main__":
    main(sys.argv[1])
