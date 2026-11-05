"""Hi-C end to end on the demo cluster: samples table, settings check, pipeline (stand-in), report, live session (libraries,
maps, distance decay, compartments against the demo's truth, TAD boundaries against the truth), export, record and an
exact repeat. Also the cooler files Everyome writes and reads."""
import json

import pytest

pytest.importorskip("h5py")

from everyome.modules.dna.hic import cool  # noqa: E402
from everyome.modules.dna.hic import demo_data as dd  # noqa: E402
from flow_helpers import call, demo_client, follow, ok  # noqa: E402,F401  (demo_client is a fixture)
from rerun_helpers import rerun, rerun_until_session_replayed, wait_for_run, wait_for_session  # noqa: E402

MID = "dna.hic"


def test_cool_files_round_trip(tmp_path):
    chroms = [("a", 95_000), ("b", 40_000)]
    b1, b2, c = [0, 0, 3, 9, 2], [0, 3, 5, 12, 11], [5, 2, 7, 1, 4]
    import numpy as np
    b1, b2, c = np.array(b1), np.array(b2), np.array(c)
    cool.write_mcool(tmp_path / "x.mcool", chroms, 10_000, [1, 2], b1, b2, c)
    assert cool.resolutions(tmp_path / "x.mcool") == [10_000, 20_000]
    C = cool.Cool(tmp_path / "x.mcool", 10_000)
    assert C.chroms == ["a", "b"] and C.nbins == 14 and C.chrom_bins("b") == (10, 14)
    m = C.matrix(0, 10, balanced=False)
    assert m[0, 3] == m[3, 0] == 2 and m[3, 5] == 7 and m.sum() == 5 + 2 * (2 + 7)
    assert C.totals() == {"cis": 5 + 2 + 7, "trans": 1 + 4, "short": 5, "long": 2 + 7}      # bins 9–12 and 2–11 cross chromosomes
    # Coarsening sums pixels within each chromosome: bins 2 and 3 of chromosome a become one 20 kb bin.
    C2 = cool.Cool(tmp_path / "x.mcool", 20_000)
    assert C2.matrix(0, 5, balanced=False)[1, 2] == 7


def test_settings_check():
    from everyome.modules.dna.hic.helpers import check
    assert check({"fasta": "/g.fa", "digestion": "dpnii", "samples": [{"fastq_2": "x"}]}, False) == []
    problems = " ".join(check({"samples": [{"fastq_2": ""}]}, False))
    assert "restriction enzyme" in problems and "FASTA" in problems and "both reads" in problems


def test_hic_end_to_end(demo_client, tmp_path):
    c = demo_client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "hic"}))
    ok(c.get(f"/api/modules/{MID}/example"))
    rows = ok(c.post(f"/api/modules/{MID}/helpers/scan", json={"path": f"{data}/fastq"}))["rows"]
    assert [r["sample"] for r in rows] == dd.SAMPLES and all(r["fastq_2"] for r in rows)

    small = {"bin_size": "160000,40000", "res_zoomify": "10000", "res_tads": "20000", "res_compartments": "80000", "res_dist_decay": "40000"}
    bad = c.post("/api/run/create", json={"module": MID, "values": {"samples": rows, "fasta": f"{data}/genome/genome.fa"}})
    assert bad.status_code == 400 and "restriction enzyme" in bad.json()["detail"]
    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"reads_dir": f"{data}/fastq", "samples": rows, "digestion": "dpnii",
                                                                        "fasta": f"{data}/genome/genome.fa", **small}}))
    rd = tmp_path / "demo_cluster/projects/hic/runs" / run["id"]
    nfp = json.loads((rd / "nf_params.json").read_text())
    assert nfp["digestion"] == "dpnii" and nfp["igenomes_ignore"] is True and nfp["res_tads"] == "20000" and "min_mapq" not in nfp
    assert (rd / "samplesheet.csv").read_text().startswith("sample,fastq_1,fastq_2\nlarva_1,")

    ok(c.post("/api/run/submit", json={}))
    wait_for_run(c)
    rep = ok(c.get("/api/run/report"))
    assert [s["sample"] for s in rep["samples"]] == dd.SAMPLES and all(s["unique"] > 500_000 and s["cis_pct"] > 95 for s in rep["samples"])
    assert "larva_1.mcool" in rep["maps"] and "larva_1.80000_balanced.cool" in rep["maps"] and rep["multiqc"] and rep["tads"]
    ok(c.post("/api/session/start"))
    wait_for_session(c, rd)

    o = call(c, "overview")
    assert o["samples"] == dd.SAMPLES and o["resolutions"] == [10_000, 20_000, 40_000, 80_000, 160_000, 320_000] and o["fasta"]
    assert o["suggest"] == {"map": 10_000, "decay": 40_000, "compartments": 80_000, "tads": 20_000} and o["compartment_files"] == [80_000]
    m = call(c, "contact_map", sample="larva_1", chrom="chr1", start=0, end=1_000_000)
    assert m["res"] == 10_000 and len(m["values"]) == len(m["values"][0]) == 100 and m["balanced"] and m["lo"] < m["hi"]
    whole = call(c, "contact_map", sample="larva_1", chrom="chr2")
    assert whole["res"] == 10_000 and len(whole["values"]) == 150
    bad = c.post("/api/s/call/contact_map", json={"sample": "larva_1", "chrom": "chrX"})
    assert bad.status_code == 400 and "No chromosome called chrX" in bad.json()["detail"]
    d = call(c, "decay")
    assert d["res"] == 40_000 and all(-2.2 < v < -0.6 for v in d["slopes"].values()), d["slopes"]

    t = json.loads((rd / "demo_truth.json").read_text())
    follow(c, "compartments")
    comp = call(c, "compartment_track")
    assert comp["source"] == "pipeline" and comp["oriented"] == "gc" and comp["flipped"]["larva_1"] == ["chr2"]
    for s in dd.SAMPLES:
        for ch, n in dd.CHROMS:
            e = comp["samples"][s][ch]
            agree = [(v > 0) == (dd.compartment_of(t, ch, i * 80_000 + 40_000) == "A") for i, v in enumerate(e) if v is not None]
            assert sum(agree) / len(agree) > 0.9, (s, ch, sum(agree) / len(agree))

    follow(c, "tads", window=5, min_strength=0.2)
    st = ok(c.get("/api/s/status"))["tads"]
    assert st["res"] == 20_000 and st["window_bp"] == 100_000
    for s in dd.SAMPLES:
        found = []
        for ch, _ in dd.CHROMS:
            tr = call(c, "tad_track", sample=s, chrom=ch)
            pos = [b["pos"] for b in tr["boundaries"]]
            truth = t["boundaries"][ch]
            found.append((sum(any(abs(p - b) <= 40_000 for p in pos) for b in truth), len(truth),
                          sum(not any(abs(p - b) <= 40_000 for b in truth) for p in pos)))
        hit, n, wrong = map(sum, zip(*found))
        assert hit >= 0.75 * n and wrong <= 3, (s, hit, n, wrong)
        assert st["hicexplorer_agree"][s] >= 60
    assert call(c, "contact_map", sample="larva_1", chrom="chr1", start=0, end=2_000_000, res=20_000)["boundaries"]

    call(c, "export")
    names = {f["name"] for f in call(c, "files")}
    assert {"final/libraries.csv", "final/distance_decay.csv", "final/larva_1_compartments_80000.bedgraph",
            "final/larva_2_tad_boundaries_20000.bed", "final/larva_2_tads_20000.bed"} <= names
    bg = (rd / "results/final/larva_1_compartments_80000.bedgraph").read_text().splitlines()
    assert bg[0].startswith("track type=bedGraph") and bg[1].startswith("chr1\t0\t80000\t")

    rec = ok(c.post("/api/run/record"))
    for phrase in ("nf-core/hic version 2.1.0", "DpnII digestion", "Bowtie 2", "iterative correction", "log–log slope",
                   "first eigenvector", "higher GC content", "diamond insulation score", "window of 5 bins (100 kb)", "HiCExplorer"):
        assert phrase in rec["methods"], phrase

    new = tmp_path / "repeat_hic"
    p = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--submit")
    assert p.returncode == 0, p.stderr
    rerun_until_session_replayed(tmp_path / "demo_cluster", rd / "record/rerun", new)
    for f in ("larva_1_compartments_80000.bedgraph", "larva_2_tad_boundaries_20000.bed", "distance_decay.csv", "libraries.csv"):
        assert (new / "results/final" / f).read_text() == (rd / "results/final" / f).read_text(), f
