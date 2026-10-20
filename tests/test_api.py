import base64
import io

import numpy as np
from fastapi.testclient import TestClient

from ndvi_monitor.api import app
from ndvi_monitor.cli import main
from ndvi_monitor.data import KEYS, make_sample

client = TestClient(app)
PNG = b"\x89PNG"


def npz_bytes(arrays):
    buf = io.BytesIO()
    np.savez(buf, **{k: arrays[k] for k in KEYS})
    return buf.getvalue()


def test_dashboard_and_health():
    assert "Vegetation Change Monitor" in client.get("/").text
    assert client.get("/api/health").json() == {"status": "ok"}


def test_sample_endpoint_returns_result_images_and_csv():
    d = client.get("/api/sample").json()
    assert d["result"]["comparison"]["usable_pixels"] == 199
    assert d["result"]["comparison"]["status"] == "decline_flagged"
    for img in d["images"].values():
        assert base64.b64decode(img).startswith(PNG)
    lines = d["csv"].splitlines()
    assert lines[0] == "row,col,ndvi_date1,ndvi_date2,change" and len(lines) == 200


def test_threshold_parameter_changes_verdict_and_bad_values_422():
    ok = client.get("/api/sample", params={"decline_threshold": 0.5}).json()
    assert ok["result"]["comparison"]["status"] == "no_decline_flagged"
    assert client.get("/api/sample", params={"decline_threshold": 0}).status_code == 422
    assert client.get("/api/sample", params={"min_usable_fraction": 2}).status_code == 422


def test_upload_valid_npz_and_rejections():
    arrays = make_sample()
    r = client.post("/api/analyze", content=npz_bytes(arrays))
    assert r.status_code == 200 and r.json()["result"]["comparison"]["usable_pixels"] == 199

    assert client.post("/api/analyze", content=b"").status_code == 400
    assert client.post("/api/analyze", content=b"not an npz").status_code == 422
    bad = dict(arrays, nir2=arrays["nir2"][:10])
    assert client.post("/api/analyze", content=npz_bytes(bad)).status_code == 422
    r = client.post("/api/analyze", content=_without(arrays, "farm"))
    assert r.status_code == 422 and "farm" in r.json()["detail"]


def _without(arrays, key):
    buf = io.BytesIO()
    np.savez(buf, **{k: arrays[k] for k in KEYS if k != key})
    return buf.getvalue()


def test_downloads():
    assert client.get("/api/sample/change.png").content.startswith(PNG)
    assert client.get("/api/sample/results.json").json()["comparison"]["usable_pixels"] == 199
    assert client.get("/api/sample/change.csv").text.startswith("row,col")
    assert client.get("/api/sample/nope.txt").status_code == 404


def test_cli_writes_outputs(tmp_path):
    assert main(["--out", str(tmp_path)]) == 0
    assert {p.name for p in tmp_path.iterdir()} == {
        "results.json", "change.csv", "date1_ndvi.png", "date2_ndvi.png", "change.png"}
    assert main(["--input", str(tmp_path / "missing.npz"), "--out", str(tmp_path)]) == 2
