"""NDVI calculation and two-date comparison.

All pixel rules live here so they can be tested without the web layer.

Rules (also documented in README.md):

* NDVI = (NIR - Red) / (NIR + Red).
* A pixel has an NDVI value only if its validity mask is True, both bands are
  finite and non-negative, and NIR + Red is non-zero. Everything else is NaN
  ("no value"), never 0, so it cannot silently pull a mean toward zero.
* Comparisons use only farm pixels that have an NDVI value on BOTH dates.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np

DISCLAIMER = (
    "A decline in NDVI is a change in measured reflectance. It does not by itself "
    "establish disease, pest damage, drought, management activity or yield loss; "
    "clouds, haze, sun angle, sensor differences and seasonal growth stage can all "
    "change NDVI. Treat a flag as a prompt for field verification."
)

STATUS_DECLINE = "decline_flagged"
STATUS_NO_DECLINE = "no_decline_flagged"
STATUS_INSUFFICIENT = "insufficient_data"


class InputError(ValueError):
    """Raised for malformed inputs (shape mismatch, wrong dimensionality...)."""


@dataclass(frozen=True)
class Config:
    # Mean change at or below -decline_threshold flags a decline.
    decline_threshold: float = 0.05
    # Pixels whose own change is at or below -pixel_decline_threshold count as declined.
    pixel_decline_threshold: float = 0.10
    # Minimum share of farm pixels usable on both dates before a verdict is given.
    min_usable_fraction: float = 0.50

    def __post_init__(self) -> None:
        if not 0 < self.decline_threshold <= 2:
            raise InputError("decline_threshold must be in (0, 2]")
        if not 0 < self.pixel_decline_threshold <= 2:
            raise InputError("pixel_decline_threshold must be in (0, 2]")
        if not 0 <= self.min_usable_fraction <= 1:
            raise InputError("min_usable_fraction must be in [0, 1]")


def compute_ndvi(red, nir, valid=None):
    """Return (ndvi, reasons).

    ndvi is float64 with NaN where no value can be assigned. reasons is a dict of
    boolean masks: ``masked`` (validity mask False), ``bad_value`` (non-finite or
    negative band) and ``zero_denominator``. They are mutually exclusive and are
    evaluated in that order, so each excluded pixel has exactly one reason.
    """
    red = np.asarray(red, dtype=np.float64)
    nir = np.asarray(nir, dtype=np.float64)
    if red.ndim != 2 or red.shape != nir.shape:
        raise InputError("red and nir must be 2-D arrays of the same shape")
    valid = np.ones(red.shape, bool) if valid is None else np.asarray(valid, dtype=bool)
    if valid.shape != red.shape:
        raise InputError("validity mask shape must match the bands")

    masked = ~valid
    with np.errstate(invalid="ignore"):
        bad = ~masked & (~np.isfinite(red) | ~np.isfinite(nir) | (red < 0) | (nir < 0))
    ok = ~masked & ~bad
    denom = np.where(ok, red + nir, 1.0)
    zero = ok & (denom == 0)
    usable = ok & ~zero

    ndvi = np.full(red.shape, np.nan)
    ndvi[usable] = (nir[usable] - red[usable]) / denom[usable]
    return ndvi, {"masked": masked, "bad_value": bad, "zero_denominator": zero}


def _mean(a):
    return float(a.mean()) if a.size else None


def _round(x, n=4):
    return None if x is None else round(float(x), n)


def compare(red1, nir1, valid1, red2, nir2, valid2, farm, config: Optional[Config] = None):
    """Compare two dates over the farm area. Returns (result, arrays)."""
    config = config or Config()
    farm = np.asarray(farm, dtype=bool)
    ndvi1, why1 = compute_ndvi(red1, nir1, valid1)
    ndvi2, why2 = compute_ndvi(red2, nir2, valid2)
    if farm.shape != ndvi1.shape or ndvi1.shape != ndvi2.shape:
        raise InputError("both dates and the farm mask must have the same shape")
    farm_px = int(farm.sum())
    if farm_px == 0:
        raise InputError("farm mask contains no pixels")

    ok1 = farm & ~np.isnan(ndvi1)
    ok2 = farm & ~np.isnan(ndvi2)
    common = ok1 & ok2

    def date_summary(ndvi, ok, why):
        n = int(ok.sum())
        return {
            "farm_pixels": farm_px,
            "valid_pixels": n,
            "valid_coverage_pct": _round(100 * n / farm_px, 2),
            "mean_ndvi_own_valid_pixels": _round(_mean(ndvi[ok])),
            "excluded_masked": int((why["masked"] & farm).sum()),
            "excluded_bad_value": int((why["bad_value"] & farm).sum()),
            "excluded_zero_denominator": int((why["zero_denominator"] & farm).sum()),
        }

    n_common = int(common.sum())
    usable_fraction = n_common / farm_px
    change = np.full(ndvi1.shape, np.nan)
    change[common] = ndvi2[common] - ndvi1[common]

    mean1 = _mean(ndvi1[common])
    mean2 = _mean(ndvi2[common])
    mean_change = None if mean1 is None else mean2 - mean1

    if n_common == 0 or usable_fraction < config.min_usable_fraction:
        status = STATUS_INSUFFICIENT
        reason = (
            "No farm pixel is valid on both dates."
            if n_common == 0
            else f"Only {100 * usable_fraction:.1f}% of farm pixels are usable on both dates "
            f"(minimum {100 * config.min_usable_fraction:.0f}%)."
        )
    elif mean_change <= -config.decline_threshold:
        status = STATUS_DECLINE
        reason = f"Mean NDVI change {mean_change:+.3f} is at or below -{config.decline_threshold:g}."
    else:
        status = STATUS_NO_DECLINE
        reason = f"Mean NDVI change {mean_change:+.3f} is above -{config.decline_threshold:g}."

    declined = common & (np.nan_to_num(change, nan=0.0) <= -config.pixel_decline_threshold)
    result = {
        "config": asdict(config),
        "date1": date_summary(ndvi1, ok1, why1),
        "date2": date_summary(ndvi2, ok2, why2),
        "comparison": {
            "comparison_area": "farm pixels with an NDVI value on both dates",
            "usable_pixels": n_common,
            "usable_pct_of_farm": _round(100 * usable_fraction, 2),
            "mean_ndvi_date1": _round(mean1),
            "mean_ndvi_date2": _round(mean2),
            "mean_change": _round(mean_change),
            "declined_pixels": int(declined.sum()),
            "declined_pct_of_usable": _round(100 * declined.sum() / n_common, 2) if n_common else None,
            "status": status,
            "status_reason": reason,
        },
        "interpretation_note": DISCLAIMER,
    }
    arrays = {"ndvi1": ndvi1, "ndvi2": ndvi2, "change": change, "farm": farm, "common": common}
    return result, arrays
