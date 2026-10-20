"""FastAPI service + single-page dashboard."""
from __future__ import annotations

import base64
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from . import render
from .core import Config, InputError, compare
from .data import load_npz_bytes, load_sample

app = FastAPI(title="Satellite Vegetation Change Monitor (PS07)", version="1.0.0")
MAX_UPLOAD = 5 * 1024 * 1024
INDEX = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


def _analyse(arrays, config: Config) -> dict:
    result, out = compare(
        arrays["red1"], arrays["nir1"], arrays["valid1"],
        arrays["red2"], arrays["nir2"], arrays["valid2"], arrays["farm"], config,
    )
    b64 = lambda b: base64.b64encode(b).decode()
    return {
        "result": result,
        "images": {
            "date1": b64(render.ndvi_png(out["ndvi1"], out["farm"])),
            "date2": b64(render.ndvi_png(out["ndvi2"], out["farm"])),
            "change": b64(render.change_png(out["change"], out["farm"])),
        },
        "csv": render.change_csv(out),
    }


def _config(decline_threshold, pixel_decline_threshold, min_usable_fraction) -> Config:
    try:
        return Config(decline_threshold, pixel_decline_threshold, min_usable_fraction)
    except InputError as exc:
        raise HTTPException(422, str(exc))


params = dict(
    decline_threshold=Query(0.05, description="Mean change <= -value flags a decline"),
    pixel_decline_threshold=Query(0.10, description="Per-pixel decline cut-off"),
    min_usable_fraction=Query(0.50, description="Min share of farm pixels usable on both dates"),
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    return INDEX


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/sample")
def sample(decline_threshold: float = params["decline_threshold"],
           pixel_decline_threshold: float = params["pixel_decline_threshold"],
           min_usable_fraction: float = params["min_usable_fraction"]):
    """Analyse the bundled SYNTHETIC two-date farm."""
    cfg = _config(decline_threshold, pixel_decline_threshold, min_usable_fraction)
    return _analyse(load_sample(), cfg)


@app.post("/api/analyze")
async def analyze(request: Request,
                  decline_threshold: float = params["decline_threshold"],
                  pixel_decline_threshold: float = params["pixel_decline_threshold"],
                  min_usable_fraction: float = params["min_usable_fraction"]):
    """Analyse an uploaded .npz (raw request body).

    Required arrays: red1, nir1, valid1, red2, nir2, valid2, farm (all 2-D, same shape).
    """
    cfg = _config(decline_threshold, pixel_decline_threshold, min_usable_fraction)
    raw = await request.body()
    if not raw:
        raise HTTPException(400, "empty upload")
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "upload too large (5 MB limit)")
    try:
        return _analyse(load_npz_bytes(raw), cfg)
    except InputError as exc:
        raise HTTPException(422, str(exc))


@app.get("/api/sample/{asset}")
def sample_download(asset: str,
                    decline_threshold: float = params["decline_threshold"],
                    pixel_decline_threshold: float = params["pixel_decline_threshold"],
                    min_usable_fraction: float = params["min_usable_fraction"]):
    """Downloads for the sample: change.png, date1.png, date2.png, results.json, change.csv."""
    import json
    data = _analyse(load_sample(), _config(decline_threshold, pixel_decline_threshold, min_usable_fraction))
    if asset in ("date1.png", "date2.png", "change.png"):
        return Response(base64.b64decode(data["images"][asset[:-4]]), media_type="image/png")
    if asset == "results.json":
        return Response(json.dumps(data["result"], indent=2), media_type="application/json")
    if asset == "change.csv":
        return PlainTextResponse(data["csv"], media_type="text/csv")
    raise HTTPException(404, "unknown asset")
