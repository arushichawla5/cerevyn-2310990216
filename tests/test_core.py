import json
from pathlib import Path

import numpy as np
import pytest

from ndvi_monitor.core import (STATUS_DECLINE, STATUS_INSUFFICIENT, STATUS_NO_DECLINE,
                               Config, InputError, compare, compute_ndvi)
from ndvi_monitor.data import make_sample

ROOT = Path(__file__).parent.parent


def grid(value, shape=(10, 10)):
    return np.full(shape, value, dtype=float)


def run(red1, nir1, v1, red2, nir2, v2, farm=None, cfg=None):
    farm = np.ones(red1.shape, bool) if farm is None else farm
    return compare(red1, nir1, v1, red2, nir2, v2, farm, cfg)


def test_known_value_nir_06_red_02_is_05():
    ndvi, _ = compute_ndvi(grid(0.2), grid(0.6))
    assert np.allclose(ndvi, 0.5)


def test_zero_denominator_is_nan_not_zero_and_counted():
    red, nir = grid(0.2), grid(0.6)
    red[0, 0] = nir[0, 0] = 0.0
    ndvi, why = compute_ndvi(red, nir)
    assert np.isnan(ndvi[0, 0])
    assert why["zero_denominator"].sum() == 1 and why["zero_denominator"][0, 0]
    assert np.isnan(ndvi).sum() == 1


def test_masked_negative_and_nan_pixels_have_no_value():
    red, nir = grid(0.2), grid(0.6)
    valid = np.ones((10, 10), bool)
    valid[1, 1] = False
    red[2, 2] = -0.1
    nir[3, 3] = np.nan
    ndvi, why = compute_ndvi(red, nir, valid)
    assert np.isnan(ndvi[[1, 2, 3], [1, 2, 3]]).all()
    assert why["masked"].sum() == 1 and why["bad_value"].sum() == 2
    assert np.isfinite(ndvi).sum() == 97


def test_fully_masked_farm_is_insufficient_not_a_number():
    a = grid(0.2), grid(0.6)
    none = np.zeros((10, 10), bool)
    result, out = run(*a, none, *a, np.ones((10, 10), bool))
    c = result["comparison"]
    assert c["status"] == STATUS_INSUFFICIENT
    assert c["usable_pixels"] == 0
    assert c["mean_change"] is None and c["mean_ndvi_date1"] is None
    assert result["date1"]["valid_coverage_pct"] == 0.0
    assert np.isnan(out["change"]).all()


def test_different_cloud_masks_use_only_pixels_valid_on_both_dates():
    # Date 2 is much greener where date 1 is cloudy; those pixels must not count.
    red1, nir1 = grid(0.2), grid(0.6)           # NDVI 0.5
    red2, nir2 = grid(0.2), grid(0.6)
    nir2[:, 5:] = 1.8                            # right half NDVI 0.8 on date 2
    v1 = np.ones((10, 10), bool)
    v1[:, 5:] = False                            # date 1 cloudy over the right half
    v2 = np.ones((10, 10), bool)
    v2[0, :] = False                             # date 2 cloudy over the top row
    result, out = run(red1, nir1, v1, red2, nir2, v2)
    c = result["comparison"]
    assert c["usable_pixels"] == 45              # left half (50) minus top row part (5)
    assert c["mean_change"] == 0.0               # greener half excluded from comparison
    assert result["date1"]["valid_pixels"] == 50 and result["date2"]["valid_pixels"] == 90
    assert not out["common"][:, 5:].any() and not out["common"][0].any()


def test_pixels_outside_farm_are_ignored():
    red1, nir1 = grid(0.2), grid(0.6)
    nir2 = grid(0.6)
    nir2[5:, :] = 0.2                            # big decline, but only outside the farm
    farm = np.zeros((10, 10), bool)
    farm[:5, :] = True
    result, _ = run(red1, nir1, None, grid(0.2), nir2, None, farm)
    assert result["comparison"]["usable_pixels"] == 50
    assert result["comparison"]["mean_change"] == 0.0
    assert result["comparison"]["status"] == STATUS_NO_DECLINE


def test_decline_flag_respects_configurable_threshold():
    red = grid(0.2)
    nir1, nir2 = grid(0.6), grid(0.5)            # 0.5 -> 0.4286, change ~ -0.0714
    loose = run(red, nir1, None, red, nir2, None, cfg=Config(decline_threshold=0.05))[0]
    strict = run(red, nir1, None, red, nir2, None, cfg=Config(decline_threshold=0.10))[0]
    assert loose["comparison"]["status"] == STATUS_DECLINE
    assert strict["comparison"]["status"] == STATUS_NO_DECLINE
    assert loose["comparison"]["mean_change"] == pytest.approx(-0.0714, abs=1e-4)


def test_low_coverage_blocks_verdict():
    red = grid(0.2)
    v = np.zeros((10, 10), bool)
    v[:3, :] = True                              # 30% usable, min is 50%
    result, _ = run(red, grid(0.6), v, red, grid(0.2), v)
    assert result["comparison"]["status"] == STATUS_INSUFFICIENT
    assert "30.0%" in result["comparison"]["status_reason"]


def test_shape_mismatch_and_empty_farm_are_rejected():
    with pytest.raises(InputError):
        compute_ndvi(grid(0.2), grid(0.6, (9, 9)))
    with pytest.raises(InputError):
        run(grid(0.2), grid(0.6), None, grid(0.2), grid(0.6), None, np.zeros((10, 10), bool))
    with pytest.raises(InputError):
        Config(decline_threshold=0)


def test_sample_matches_hand_derived_numbers_and_stored_expectation():
    a = make_sample()
    result, _ = compare(a["red1"], a["nir1"], a["valid1"], a["red2"], a["nir2"], a["valid2"], a["farm"])
    c = result["comparison"]
    # 240 farm px - 20 cloud (date 1) - 20 cloud (date 2) - 1 zero denominator = 199
    assert c["usable_pixels"] == 199
    assert c["declined_pixels"] == 36            # the 6x6 patch
    assert result["date1"]["excluded_zero_denominator"] == 1
    assert c["status"] == STATUS_DECLINE
    assert result == json.loads((ROOT / "sample_data" / "expected_results.json").read_text())


def test_sample_generation_is_reproducible():
    a, b = make_sample(), make_sample()
    assert all(np.array_equal(a[k], b[k]) for k in a)
