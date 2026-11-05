"""Variant calling end to end on the demo cluster: samples table, pipeline (sarek stand-in), report, session (callers,
filters against the known variants, one variant, groups find the planted mutant region), export, record and an exact
repeat. Also the pipeline parameters Everyome always sets (the user's own genome, never sarek's human reference)."""
import json

from everyome.modules.dna.variants.demo_data import truth
from everyome.modules.dna.variants.engine import read_vcf
from flow_helpers import call, demo_client, ok  # noqa: F401  (demo_client is a fixture)
from rerun_helpers import rerun, rerun_until_session_replayed, wait_for_run, wait_for_session

MID = "dna.variants"


def test_variants_end_to_end(demo_client, tmp_path):
    c = demo_client
    ok(c.post("/api/connect", json={"mode": "demo"}))
    data = f"{tmp_path}/demo_cluster/data/{MID}"
    ok(c.post("/api/project/create", json={"name": "var"}))
    rows = ok(c.post(f"/api/modules/{MID}/helpers/scan", json={"path": f"{data}/fastq"}))["rows"]
    assert [r["group"] for r in rows] == ["mut"] * 3 + ["wt"] * 3 and all(r["lane"] == "L001" and r["patient"] == r["sample"] for r in rows)

    run = ok(c.post("/api/run/create", json={"module": MID, "values": {"reads_dir": f"{data}/fastq", "samples": rows,
                                                                        "fasta": f"{data}/genome/genome.fa"}}))
    rd = tmp_path / "demo_cluster/projects/var/runs" / run["id"]
    nfp = json.loads((rd / "nf_params.json").read_text())
    # Intent: the user's genome only (no human iGenome), two callers, no steps that need known variant sites.
    assert nfp["genome"] is None and nfp["igenomes_ignore"] is True and nfp["fasta"].endswith("genome.fa")
    assert nfp["tools"] == "haplotypecaller,deepvariant" and nfp["skip_tools"] == "baserecalibrator,haplotypecaller_filter"
    assert (rd / "samplesheet.csv").read_text().startswith("patient,sample,lane,fastq_1,fastq_2\nmut_1,mut_1,L001,")
    form = ok(c.get(f"/api/modules/{MID}"))
    assert "genome" not in {f["id"] for f in form.get("params", form.get("settings", []))}

    ok(c.post("/api/run/submit", json={}))
    wait_for_run(c)
    rep = ok(c.get("/api/run/report"))
    assert len(rep["vcfs"]) == 12 and {v["caller"] for v in rep["vcfs"]} == {"haplotypecaller", "deepvariant"}
    assert len(rep["coverage"]) == 6 and rep["multiqc"]

    ok(c.post("/api/session/start"))
    wait_for_session(c, rd)
    o = call(c, "overview")
    assert o["callers"] == ["haplotypecaller", "deepvariant"] and o["samples"][:3] == ["mut_1", "mut_2", "mut_3"]
    assert all(len(a["by"]) == 2 and a["by"][1] > a["by"][0] for a in o["agree"])         # most variants found by both
    # The deepvariant VCF really has RefCall records (0/0, failed), which never count as calls.
    _, _, recs = read_vcf(next(rd.glob("results/variant_calling/deepvariant/mut_1/*.vcf.gz")))
    assert any(not r[5] and r[6][0][0] == 0 for r in recs)

    true = {(v["chrom"], v["pos"], v["ref"], v["alt"]) for v in truth()}
    loose = call(c, "apply_filters", min_qual=0, min_dp=0, min_gq=0, pass_only=False)
    strict = call(c, "apply_filters", agree=2)
    v = call(c, "variants", n=5000)
    kept = {(r["chrom"], r["pos"], r["ref"], r["alt"]) for r in v["rows"]}
    # Intent: both callers agreeing at QUAL 30, depth 10, GQ 20 keeps almost every true variant and no false ones.
    assert len(kept - true) == 0 and len(kept & true) >= 0.95 * len(true), (len(kept - true), len(kept & true), len(true))
    assert loose["kept"] > strict["kept"] and strict["titv"] > loose["titv"]
    g = {(x["chrom"], x["pos"]): x for x in v["rows"]}
    first = truth()[0]
    assert g[(first["chrom"], first["pos"])]["gt"] == [first["gt"][s] for s in v["samples"]]
    one = call(c, "variant", i=v["rows"][0]["i"])
    assert {x["caller"] for x in one["calls"]} == {"haplotypecaller", "deepvariant"} and all(x["dp"] > 0 for x in one["calls"])
    bad = c.post("/api/s/call/apply_filters", json={"agree": 3})
    assert bad.status_code == 400 and "Only 2 callers" in bad.json()["detail"]
    call(c, "apply_filters", agree=2)

    r = call(c, "groups", a="mut", b="wt")
    planted = {(x["chrom"], x["pos"]) for x in truth() if x["kind"] == "mutant"}
    sep = {(x["chrom"], x["pos"]) for x in call(c, "variants", only="separating", n=500)["rows"]}
    assert planted <= sep and r["carried_by_a"] >= 10
    chr2 = next(w for w in r["windows"] if w["chrom"] == "chr2")
    peak = max(range(len(chr2["separating"])), key=lambda i: chr2["separating"][i])
    assert 18_000 <= (peak + 0.5) * chr2["size"] <= 24_000                                  # the cluster is the planted region

    call(c, "export")
    names = {f["name"] for f in call(c, "files")}
    assert {"final/variants_filtered.vcf", "final/variants_filtered.csv", "final/separating_mut_vs_wt.csv"} <= names
    vcf = (rd / "results/final/variants_filtered.vcf").read_text()
    assert '"agree": 2' in vcf and vcf.count("\nchr") == strict["kept"]

    rec = ok(c.post("/api/run/record"))
    for phrase in ("nf-core/sarek version 3.11.0", "GATK HaplotypeCaller (McKenna et al., 2010) and DeepVariant (Poplin et al., 2018)",
                   "Base quality score recalibration was not run", "called by both HaplotypeCaller and DeepVariant",
                   "variant quality (QUAL) of at least 30", "Variants separating mut (mut_1, mut_2 and mut_3) from wt"):
        assert phrase in rec["methods"], phrase

    new = tmp_path / "repeat_var"
    p = rerun(tmp_path / "demo_cluster", rd / "record/rerun", new, "--submit")
    assert p.returncode == 0, p.stderr
    rerun_until_session_replayed(tmp_path / "demo_cluster", rd / "record/rerun", new)
    for f in ("variants_filtered.vcf", "variants_filtered.csv", "separating_mut_vs_wt.csv"):
        assert (new / "results/final" / f).read_text() == (rd / "results/final" / f).read_text(), f
