"""Command line: python -m ndvi_monitor.cli [--input file.npz] --out outputs/"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import render
from .core import Config, InputError, compare
from .data import load_npz_bytes, load_sample


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Compare NDVI between two dates over a farm area.")
    p.add_argument("--input", help=".npz with red1,nir1,valid1,red2,nir2,valid2,farm (default: bundled synthetic sample)")
    p.add_argument("--out", default="outputs", help="output directory")
    p.add_argument("--decline-threshold", type=float, default=0.05)
    p.add_argument("--pixel-decline-threshold", type=float, default=0.10)
    p.add_argument("--min-usable-fraction", type=float, default=0.50)
    a = p.parse_args(argv)
    try:
        cfg = Config(a.decline_threshold, a.pixel_decline_threshold, a.min_usable_fraction)
        arrays = load_npz_bytes(Path(a.input).read_bytes()) if a.input else load_sample()
        result, out = compare(arrays["red1"], arrays["nir1"], arrays["valid1"],
                              arrays["red2"], arrays["nir2"], arrays["valid2"], arrays["farm"], cfg)
    except (InputError, OSError) as exc:
        print(f"error: {exc}")
        return 2
    d = Path(a.out)
    d.mkdir(parents=True, exist_ok=True)
    (d / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (d / "change.csv").write_text(render.change_csv(out), encoding="utf-8")
    (d / "date1_ndvi.png").write_bytes(render.ndvi_png(out["ndvi1"], out["farm"]))
    (d / "date2_ndvi.png").write_bytes(render.ndvi_png(out["ndvi2"], out["farm"]))
    (d / "change.png").write_bytes(render.change_png(out["change"], out["farm"]))
    c = result["comparison"]
    print(f"status={c['status']} mean_change={c['mean_change']} usable={c['usable_pixels']} "
          f"({c['usable_pct_of_farm']}%) -> {d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
