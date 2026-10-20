"""PNG heatmaps and CSV export."""
from __future__ import annotations

import csv
import io

import numpy as np
from PIL import Image

SCALE = 16  # pixels per cell in the PNG

OUTSIDE = (24, 24, 32)     # not part of the farm
NO_VALUE = (200, 60, 200)  # on the farm but no NDVI value (cloud/invalid/zero denominator)


def _png(rgb: np.ndarray) -> bytes:
    img = Image.fromarray(rgb.astype(np.uint8), "RGB").resize(
        (rgb.shape[1] * SCALE, rgb.shape[0] * SCALE), Image.NEAREST
    )
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _gray(values, lo, hi, farm, show_nan_on_farm):
    """Grayscale: lo -> black, hi -> white. NaN on farm is magenta, outside is dark."""
    g = np.nan_to_num((values - lo) / (hi - lo), nan=0.0).clip(0, 1) * 255
    rgb = np.dstack([g, g, g])
    rgb[~farm] = OUTSIDE
    if show_nan_on_farm:
        rgb[farm & np.isnan(values)] = NO_VALUE
    return rgb


def ndvi_png(ndvi, farm) -> bytes:
    """NDVI in [-0.2, 1.0] as grayscale (white = dense vegetation)."""
    return _png(_gray(ndvi, -0.2, 1.0, farm, True))


def change_png(change, farm) -> bytes:
    """Change in [-0.6, +0.6]: mid-gray = no change, dark = decline, light = increase."""
    return _png(_gray(change, -0.6, 0.6, farm, True))


def change_csv(arrays) -> str:
    """One row per usable pixel (farm and valid on both dates)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["row", "col", "ndvi_date1", "ndvi_date2", "change"])
    for r, c in zip(*np.nonzero(arrays["common"])):
        w.writerow([
            int(r), int(c),
            f"{arrays['ndvi1'][r, c]:.4f}", f"{arrays['ndvi2'][r, c]:.4f}",
            f"{arrays['change'][r, c]:.4f}",
        ])
    return buf.getvalue()
