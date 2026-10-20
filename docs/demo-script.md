# Demo script (3-5 minutes)

Record your screen while following this. Each step maps to a required demonstration check.

1. **Setup (20 s)** - `pip install -r requirements-dev.txt`, then `python -m pytest -v`: show 17 passed.
2. **Known value (30 s)** - open `tests/test_core.py::test_known_value_nir_06_red_02_is_05`; say NIR 0.6, Red 0.2
   gives 0.5.
3. **Dashboard (60 s)** - `uvicorn ndvi_monitor.api:app --port 8000`, open the page. Point out: the two dates and
   their valid coverage (91.25% / 91.67%), the magenta cloud blocks in different places, the single
   magenta pixel (zero denominator), the dark patch in the change map.
4. **Same comparison area (45 s)** - table: usable pixels 199 = 240 - 20 - 20 - 1; mean NDVI of both dates is
   computed on those 199 only.
5. **Threshold (45 s)** - set decline threshold 0.10: verdict flips to "no decline flagged" because the loss is
   diluted over the field, while "Declined pixels" still shows 36. Explain why both numbers exist.
6. **Min usable fraction (30 s)** - set it to 0.90: "insufficient data" instead of a number.
7. **Bad input (20 s)** - upload any non-`.npz` file: readable error, HTTP 422.
8. **Downloads (20 s)** - download `results.json`, `change.csv`, `change.png`.
9. **Caveat (20 s)** - read the interpretation note: decline is not diagnosis.
