"""Nextflow modules: forms from the pipeline's schema, and the head job, config and parameter file Everyome writes."""
import json

from everyome.core import modules, nfschema, runs
from everyome.core.manifest import check_values

M = modules.discover()[0]["rna.bulk_de"]
SCHEMA = json.loads((M.dir / "pipeline/nextflow_schema.json").read_text())


def test_every_pipeline_parameter_becomes_a_field():
    names = {n for d in SCHEMA["$defs"].values() for n in d["properties"]}
    got = {f.id for f in M.params if f.pipeline}
    skipped = names - got
    assert {"input", "outdir", "email"} <= skipped
    assert len(skipped) < 20 and {"aligner", "genome", "fasta", "gtf", "skip_trimming", "min_trimmed_reads"} <= got


def test_types_defaults_and_groups():
    f = {x.id: x for x in M.params}
    assert f["aligner"].type == "choice" and f["aligner"].default == "star_salmon" and "star_rsem" in f["aligner"].choices
    assert f["fasta"].type == "file" and f["min_trimmed_reads"].type == "int" and f["min_trimmed_reads"].default == 10000
    assert f["skip_trimming"].type == "bool" and f["aligner"].group == "Alignment options"
    assert f["pseudo_aligner"].choices[0] == ""          # optional choice: empty leaves it to the pipeline
    assert any(x.advanced for x in M.params)


def test_unknown_types_are_skipped():
    assert nfschema.field_for("x", {"type": "object"}, "g", False) is None


def run_for(values, demo=False):
    vals, errors = check_values(M, values)
    assert not errors, errors
    return {"id": "r1", "dir": "/proj/runs/r1", "user": "hh2891", "values": vals, "resources": {"cpus": 2, "partition": "short"}, "demo": demo,
            "pipelines_dir": "/site/pipelines"}


SAMPLES = [{"sample": "a_1", "fastq_1": "/d/a_1_R1.fastq.gz", "fastq_2": "/d/a_1_R2.fastq.gz", "strandedness": "auto", "condition": "a"},
           {"sample": "b_1", "fastq_1": "/d/b_1_R1.fastq.gz", "fastq_2": "", "strandedness": "reverse", "condition": "b"}]


def test_pipeline_files_pass_only_changes():
    run = run_for({"samples": SAMPLES, "aligner": "star_rsem", "genome": "GRCh38", "min_trimmed_reads": 10000})
    files = runs.pipeline_files(run, M)
    assert files["samplesheet.csv"].splitlines() == ["sample,fastq_1,fastq_2,strandedness",
                                                     "a_1,/d/a_1_R1.fastq.gz,/d/a_1_R2.fastq.gz,auto", "b_1,/d/b_1_R1.fastq.gz,,reverse"]
    p = json.loads(files["nf_params.json"])
    assert p == {"aligner": "star_rsem", "genome": "GRCh38", "input": "/proj/runs/r1/samplesheet.csv", "outdir": "/proj/runs/r1/results"}
    cfg = files["nextflow.config"]
    assert "process.executor = 'slurm'" in cfg and "process.queue = 'short'" in cfg
    assert "jobName = { 'Claude_hh2891_everyome_rna_bulk_de_' + task.process.tokenize(':')[-1] }" in cfg


def test_head_job_is_pinned_and_named():
    run = run_for({"samples": SAMPLES})
    s = runs.stage_script(run, M, M.stages[0], "/opt/py")
    assert "#SBATCH --job-name=Claude_hh2891_everyome_rna_bulk_de_01_pipeline" in s
    # Intent: the cluster runs the copy Everyome installed, offline, with the shipped plugins and a shared container folder.
    assert "nextflow run /site/pipelines/nf-core-rnaseq-3.27.0 -profile apptainer" in s and "-resume" in s and "-with-trace /proj/runs/r1/trace.txt" in s
    assert "github" not in s and " -r " not in s
    for line in ("export NXF_OFFLINE=true", "export NXF_PLUGINS_DIR=/site/pipelines/plugins", "export NXF_APPTAINER_CACHEDIR=/site/pipelines/containers"):
        assert line in s, line
    named = runs.stage_script({**run, "job_prefix": "lab"}, M, M.stages[0], "/opt/py")
    assert "#SBATCH --job-name=lab_hh2891_everyome_rna_bulk_de_01_pipeline" in named
    assert "#SBATCH --job-name=hh2891_everyome_rna_bulk_de_01_pipeline" in runs.stage_script({**run, "job_prefix": ""}, M, M.stages[0], "/opt/py")
    demo = runs.stage_script(run_for({"samples": SAMPLES}, demo=True), M, M.stages[0], "/opt/py")
    assert "nextflow" not in demo.split("export EVERYOME_DEMO=1")[1] and "demo_pipeline" in demo


def test_samples_table_checks():
    _, errors = check_values(M, {"samples": [{**SAMPLES[0], "strandedness": "sideways"}]})
    assert "forward, reverse, unstranded or auto" in errors["samples"]


def test_untouched_yes_no_settings_are_not_changes():
    run = run_for({"samples": SAMPLES})
    assert json.loads(runs.pipeline_files(run, M)["nf_params.json"]).keys() == {"input", "outdir"}
    vals, _ = check_values(M, {"samples": SAMPLES, "skip_trimming": False, "arm": False})
    assert [f.id for f in M.params if vals.get(f.id) != f.default] == []


def test_fixed_parameters_are_always_passed_and_not_offered(tmp_path):
    import shutil

    import pytest

    from everyome.core.manifest import ManifestError, load
    d = tmp_path / "m"
    shutil.copytree(M.dir, d)
    y = (d / "module.yaml").read_text().replace("  profile: apptainer\n", "  profile: apptainer\n  fixed: {genome: null, igenomes_ignore: true}\n", 1)
    (d / "module.yaml").write_text(y)
    m = load(d / "module.yaml")
    assert not {"genome", "igenomes_ignore"} & {f.id for f in m.params}
    vals, errors = check_values(m, {"samples": SAMPLES})
    assert not errors, errors
    run = {"id": "r1", "dir": "/proj/runs/r1", "user": "hh2891", "values": vals, "resources": {"cpus": 2}, "demo": False, "pipelines_dir": "/p"}
    p = json.loads(runs.pipeline_files(run, m)["nf_params.json"])
    assert p["genome"] is None and p["igenomes_ignore"] is True
    (d / "module.yaml").write_text(y.replace("igenomes_ignore: true", "no_such_param: 1"))
    with pytest.raises(ManifestError, match="batch.fixed names unknown pipeline parameters: no_such_param"):
        load(d / "module.yaml")


def test_required_setting_with_a_default_falls_back_to_it():
    sarek = modules.discover()[0]["dna.variants"]
    step = next(f for f in sarek.params if f.id == "step")
    assert step.required and step.default == "mapping"
    vals, errors = check_values(sarek, {"samples": [{"patient": "a", "sample": "a", "lane": "L1", "fastq_1": "/d/a_R1.fastq.gz"}]})
    assert vals["step"] == "mapping" and "step" not in errors


def test_derived_files_are_written_unless_the_user_gives_one():
    ribo = modules.discover()[0]["rna.riboseq"]
    rows = [{"sample": f"{c}_{t}", "fastq_1": f"/d/{c}_{t}_R1.fastq.gz", "strandedness": "auto", "type": t, "pair": c, "condition": c.split("_")[0]}
            for c in ("ctl_1", "trt_1") for t in ("riboseq", "rnaseq")]
    for given, expect in (("", "/proj/runs/r1/contrasts.csv"), ("/mine/contrasts.csv", "/mine/contrasts.csv")):
        vals, errors = check_values(ribo, {"samples": rows, "contrasts": given})
        assert not errors, errors
        run = {"id": "r1", "dir": "/proj/runs/r1", "user": "hh2891", "values": vals, "resources": {}, "demo": False, "pipelines_dir": "/p"}
        files = runs.pipeline_files(run, ribo)
        assert json.loads(files["nf_params.json"])["contrasts"] == expect
        assert ("contrasts.csv" in files) == (not given)
