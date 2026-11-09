"""qPCR analysis end to end with no cluster at all ("This computer"): plate checks, efficiencies, reference genes,
fold changes against the planted answers in the demo plate, export, record and an exact repeat. Also reading
instrument exports with other column names, Excel files and no task column.

Needs the molbio extra (pip install -e ".[molbio]"); skipped without it.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("pandas")
pytest.importorskip("scipy")

from fastapi.testclient import TestClient  # noqa: E402

from everyome.core import server  # noqa: E402
from everyome.modules.molbio.qpcr.engine import read_plate  # noqa: E402

MID = "molbio.qpcr"


def ok(r):
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture()
def client(tmp_path):
    server.S.local_root = tmp_path / "Everyome"
    c = TestClient(server.app)
    yield c
    c.post("/api/disconnect")


def call(c, method, **kw):
    return ok(c.post(f"/api/s/call/{method}", json=kw))


def test_qpcr_with_no_cluster(client, tmp_path):
    c = client
    ok(c.post("/api/connect", json={"mode": "local"}))
    example = tmp_path / "Everyome/examples" / MID / "demo_qpcr_plate.csv"
    assert example.exists()
    ok(c.post("/api/project/create", json={"name": "knockdown"}))
    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"results_file": str(example)}}))
    assert run["jobs"] == {}
    assert ok(c.post("/api/session/start"))["local"] is True

    o = call(c, "overview")
    assert o["wells"] == 145 and o["standards"] == 50 and o["ntc"] == 5 and o["control"] == "control"
    assert o["samples"] == ["control_1", "control_2", "control_3", "treated_1", "treated_2", "treated_3"]
    assert set(o["references"]) == {"ACTB", "EF1a", "GAPDH"}                  # guessed from common names

    # The plate: the planted bad replicate is flagged and suggested; one control gives a late signal.
    p = call(c, "plate")
    assert p["size"] == 384
    flagged = [r for r in p["replicates"] if r["flag"]]
    assert [(r["sample"], r["target"]) for r in flagged] == [("treated_2", "Wnt3")]
    odd = flagged[0]["suggest"]
    assert {n["target"]: n["verdict"] for n in p["ntc"]} == {"EF1a": "clean", "GAPDH": "late signal", "ACTB": "clean", "Wnt3": "clean", "Bra": "clean"}
    assert c.post("/api/s/call/exclude", json={"wells": ["Z99"]}).status_code == 400
    call(c, "exclude", wells=[odd])
    assert not [r for r in call(c, "plate")["replicates"] if r["flag"]]

    # Efficiencies from the standard curves, close to the planted ones.
    eff = {t["target"]: t for t in call(c, "efficiencies")["targets"]}
    for t, true in {"EF1a": 0.98, "GAPDH": 0.95, "ACTB": 0.97, "Wnt3": 0.92, "Bra": 1.00}.items():
        assert abs(eff[t]["efficiency"] - true) < 0.03 and eff[t]["r2"] > 0.99 and eff[t]["source"] == "standard curve", t

    # geNorm: the two steady references come out on top; ACTB (which changes with treatment) and the targets below.
    ref = call(c, "references")
    assert [g["target"] for g in ref["genes"][:2]] == ["EF1a", "GAPDH"] or [g["target"] for g in ref["genes"][:2]] == ["GAPDH", "EF1a"]
    assert ref["genes"][2]["target"] == "ACTB"
    assert c.post("/api/s/call/set_references", json={"genes": ["Nope"]}).status_code == 400
    call(c, "set_references", genes=["EF1a", "GAPDH"])
    bad = c.post("/api/s/call/set_groups", json={"groups": {}, "control": "nobody"})
    assert bad.status_code == 400 and "No group called nobody" in bad.json()["detail"]
    call(c, "set_groups", groups={"control_1": "control"}, control="control")

    # Fold changes: Wnt3 up about 4×, Bra down about 2×, ACTB (no longer a reference) up.
    ex = {r["target"]: r for r in call(c, "expression")["comparisons"]}
    assert set(ex) == {"ACTB", "Bra", "Wnt3"}
    assert 3 < ex["Wnt3"]["fold_change"] < 5.5 and ex["Wnt3"]["ci_low"] > 1 and ex["Wnt3"]["p_adj"] < 0.05
    assert 0.3 < ex["Bra"]["fold_change"] < 0.7 and ex["Bra"]["ci_high"] < 1
    assert ex["ACTB"]["fold_change"] > 1.3

    files = call(c, "export")["files"]
    assert files == ["efficiencies.csv", "excluded_wells.csv", "fold_changes.csv", "relative_expression.csv", "replicates.csv"]
    fc = c.get("/api/s/download", params={"name": "fold_changes.csv"})
    assert fc.status_code == 200 and "Wnt3" in fc.text

    rec = ok(c.post("/api/run/record"))
    for phrase in (f"1 well ({odd}) was left out", "E = 10^(−1/slope) − 1", "the reference genes EF1a and GAPDH",
                   "geNorm M values (Vandesompele et al., 2002)", "relative to the mean of the control samples", "Benjamini–Hochberg"):
        assert phrase in rec["methods"], phrase

    # Repeat from the bundle: no jobs, just the replayed steps, the same tables.
    rd = tmp_path / "Everyome/projects/knockdown/runs" / run["id"]
    new = tmp_path / "repeat_qpcr"
    args = [sys.executable, "-m", "everyome.core.rerun", str(rd / "record/rerun"), str(new)]
    p1 = subprocess.run(args, capture_output=True, text=True, env=os.environ)
    assert p1.returncode == 0 and "no cluster stages" in p1.stdout, p1.stderr
    p2 = subprocess.run(args + ["--session"], capture_output=True, text=True, env=os.environ)
    assert p2.returncode == 0, p2.stderr
    for f in ("fold_changes.csv", "relative_expression.csv", "excluded_wells.csv"):
        assert (new / "results" / f).read_text() == (rd / "results" / f).read_text(), f


def test_reading_other_exports(tmp_path):
    """Bio-Rad-style names, no task column (standards from quantities, NTC from the name), Excel and bad files."""
    pd = pytest.importorskip("pandas")
    text = ("Well\tContent\tSample\tGene\tCq\tStarting Quantity (SQ)\n"
            "A01\tUnkn-01\tmock_1\tactin\t18.2\t\nA02\tUnkn-01\tmock_1\tactin\tN/A\t\n"
            "B01\tStd-01\tstd\tactin\t15.1\t100\nC01\tNTC\tNTC\tactin\t\t\n")
    f = tmp_path / "cfx.txt"
    f.write_text(text)
    df = read_plate(f)
    assert df.task.tolist() == ["unknown", "unknown", "standard", "ntc"] and df.cq.isna().tolist() == [False, True, False, True]
    assert df.quantity.iloc[2] == 100

    g = tmp_path / "plain.csv"
    g.write_text("Sample,Target,Ct,Quantity\na_1,gapdh,20,\nstd,gapdh,15,10\nwater,gapdh,Undetermined,\n")
    assert read_plate(g).task.tolist() == ["unknown", "standard", "ntc"]

    pytest.importorskip("openpyxl")
    x = tmp_path / "plate.xlsx"
    pd.DataFrame([["Run details", "", "", ""], ["Well Position", "Sample Name", "Target Name", "CT"], ["A1", "s_1", "t", "21.5"]]).to_excel(x, header=False, index=False)
    assert read_plate(x).cq.tolist() == [21.5]

    bad = tmp_path / "bad.csv"
    bad.write_text("Sample,Target,Value\na,b,1\n")
    with pytest.raises(ValueError, match="Couldn't find a Cq or Ct column"):
        read_plate(bad)
