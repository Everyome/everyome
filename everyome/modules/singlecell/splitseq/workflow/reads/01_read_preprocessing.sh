#!/usr/bin/env bash
# =============================================================================
# Stages 01–05: raw FASTQ -> unaligned paired BAM, per sublibrary × run.
#
#   01 qc        FastQC on raw reads
#   02 trim      cutadapt adapter trim + R2 truncation to a fixed length
#   03 dephase   keep R2 reads whose barcode anchor is in the expected register
#   04 repair    restore R1/R2 pairing after R2 filtering (pairfq)
#   05 tobam     paired FASTQ -> unaligned BAM (Picard FastqToSam) + read counts
#
# Usage:  bash workflow/reads/01_read_preprocessing.sh [stage ...]
#         (no arguments = run all stages in order)
# =============================================================================
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

QC_DIR="$OUT_DIR/qc"
mkdir -p "$WORK_DIR" "$OUT_DIR" "$QC_DIR/fastqc_raw"

raw()  { echo "$RAW_DIR/${1}_${2}_${3}.fq.gz"; }   # raw <sublib> <run> <R1|R2>
work() { echo "$WORK_DIR/${1}_${2}"; }             # per-sample intermediate prefix

# --- 01 QC -------------------------------------------------------------------
stage_qc() {
  require fastqc
  log "01 qc: FastQC on raw reads"
  # Intent: one FastQC report per raw file; review before trimming.
  run_named 01_fastqc fastqc -t "$THREADS" -o "$QC_DIR/fastqc_raw" "$RAW_DIR"/*.fq.gz
}

# --- 02 Trim -----------------------------------------------------------------
trim_one() {
  local s="$1" r="$2" p; p="$(work "$s" "$r")"
  # Intent: remove read-through adapter from R1 and drop reads too short to map.
  run_named "02_trim_R1_${s}_${r}" cutadapt -j "$THREADS" -m "$R1_MIN_LEN" \
    -b "$R1_ADAPTER" -o "${p}_R1_trim.fq" "$(raw "$s" "$r" R1)" > "${p}_R1_cutadapt.log"
  # Intent: trim Tn5 adapter and Ns from R2, keep reads long enough to hold
  # UMI + 3 barcodes, then truncate to R2_TRUNCATE nt so the dephasing anchor
  # sits at a fixed distance from the 3' end.
  run_named "02_trim_R2_${s}_${r}" cutadapt -j "$THREADS" -m "$R2_MIN_LEN" --trim-n \
    -b "$R2_ADAPTER" --length "$R2_TRUNCATE" \
    -o "${p}_R2_trim.fq" "$(raw "$s" "$r" R2)" > "${p}_R2_cutadapt.log"
}
stage_trim() { require cutadapt; log "02 trim"; for_each_sample trim_one; }

# --- 03 Dephase --------------------------------------------------------------
dephase_one() {
  local s="$1" r="$2" p; p="$(work "$s" "$r")"
  # Intent: test the regex on the SEQUENCE line of each 4-line record only, so
  # quality strings can never match and records stay intact.
  awk -v pat="$DEPHASE_REGEX" '
    NR % 4 == 1 { h = $0 }
    NR % 4 == 2 { s = $0 }
    NR % 4 == 3 { q = $0 }
    NR % 4 == 0 { if (s ~ pat) { print h; print s; print q; print $0 } }
  ' "${p}_R2_trim.fq" > "${p}_R2_dephased.fq"
}
stage_dephase() { log "03 dephase"; for_each_sample dephase_one; }

# --- 04 Re-pair --------------------------------------------------------------
repair_one() {
  local s="$1" r="$2" p; p="$(work "$s" "$r")"
  # Intent: R2 filtering orphaned some R1 reads; keep only reads present in both.
  run_named "04_pairfq_${s}_${r}" "$PAIRFQ" makepairs \
    -f "${p}_R1_trim.fq" -r "${p}_R2_dephased.fq" \
    -fp "${p}_R1_pair.fq" -rp "${p}_R2_pair.fq" \
    -fs "${p}_R1_single.fq" -rs "${p}_R2_single.fq"
  gzip -f "${p}_R1_pair.fq" "${p}_R2_pair.fq"
}
stage_repair() {
  [[ -x "$PAIRFQ" ]] || chmod +x "$PAIRFQ"
  log "04 repair"; for_each_sample repair_one
}

# --- 05 FASTQ -> unaligned BAM -----------------------------------------------
tobam_one() {
  local s="$1" r="$2" p sm; p="$(work "$s" "$r")"
  sm="$s"          # BAM sample tag = sublibrary name
  mkdir -p "$OUT_DIR/$s" "$WORK_DIR/tmp_${s}_${r}"
  # Intent: package pairs as an unaligned BAM, the input the Split-seq toolbox expects.
  run_named "05_fastqtosam_${s}_${r}" picard FastqToSam \
    F1="${p}_R1_pair.fq.gz" F2="${p}_R2_pair.fq.gz" \
    O="$OUT_DIR/$s/${s}_${r}.bam" SM="$sm" TMP_DIR="$WORK_DIR/tmp_${s}_${r}"
}
stage_tobam() {
  require picard samtools
  log "05 tobam"; for_each_sample tobam_one
  # Intent: one table of read-pair counts per BAM for the run report.
  local s r
  { echo -e "sublib\trun\treads"
    for s in "${SUBLIBS[@]}"; do for r in "${RUNS[@]}"; do
      echo -e "$s\t$r\t$(samtools view -c "$OUT_DIR/$s/${s}_${r}.bam")"
    done; done; } > "$QC_DIR/unaligned_read_counts.tsv"
  if [[ "$KEEP_INTERMEDIATES" != 1 ]]; then
    rm -f "$WORK_DIR"/*_trim.fq "$WORK_DIR"/*_dephased.fq "$WORK_DIR"/*_single.fq
  fi
}

# --- Driver ------------------------------------------------------------------
STAGES=("${@:-qc trim dephase repair tobam}")
for st in ${STAGES[*]}; do "stage_$st"; done
log "01_read_preprocessing done"
