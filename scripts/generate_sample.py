"""Regenerate sample_data/ (synthetic). Run from the repository root:
python scripts/generate_sample.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from ndvi_monitor.core import compare  # noqa: E402
from ndvi_monitor.data import ORIGIN, make_sample, save_npz  # noqa: E402

out = ROOT / "sample_data"
out.mkdir(exist_ok=True)
a = make_sample()
save_npz(a, out / "farm_two_dates.npz")
result, _ = compare(a["red1"], a["nir1"], a["valid1"], a["red2"], a["nir2"], a["valid2"], a["farm"])
(out / "expected_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
(out / "README.md").write_text(
    f"# Sample data\n\n{ORIGIN}\n\n"
    "- `farm_two_dates.npz` - 20x20 arrays: red1, nir1, valid1, red2, nir2, valid2, farm.\n"
    "- `expected_results.json` - output of the default configuration (checked by tests).\n\n"
    "Built-in scenario: 240 farm pixels; date 1 has a 20-pixel cloud, one zero-denominator pixel "
    "(red = nir = 0); date 2 has a different 20-pixel cloud and a 6x6 patch (36 px) whose NDVI falls "
    "from about 0.70 to about 0.30. Hand-derived: usable on both dates = 240 - 20 - 20 - 1 = 199.\n",
    encoding="utf-8",
)
print("wrote", out)
