#!/usr/bin/env bash
# =============================================================================
# Stages 06–08: unaligned BAM -> per-sublibrary digital gene expression matrix.
#
#   06 align     Split-seq toolbox: barcode/UMI tagging, STAR alignment,
#                gene/function tagging (writes <sample>_gft.bam)
#   07 merge     merge the sequencing runs of each sublibrary; count reads per
#                genomic region (XF tag)
#   08 dge       DigitalExpression matrix + cell count, UMI duplication, elbow data
#
# Usage:  bash workflow/reads/02_align_merge_dge.sh [stage ...]
# =============================================================================
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

QC_DIR="$OUT_DIR/qc"
mkdir -p "$QC_DIR"

# --- 06 Align & tag ----------------------------------------------------------
align_one() {
  local s="$1" r="$2" abs_toolbox abs_index abs_fasta
  abs_toolbox="$(realpath "$SPLITSEQ_TOOLBOX")"
  abs_index="$(realpath "$STAR_INDEX")"
  abs_fasta="$(realpath "$REF_FASTA")"
  # Intent: the toolbox writes into the working directory, so run it inside
  # the sublibrary folder to keep outputs together.
  ( cd "$OUT_DIR/$s" && run_named "06_splitseq_${s}_${r}" bash "$abs_toolbox" \
      -g "$abs_index" -r "$abs_fasta" -n "$EXPECTED_CELLS" "${s}_${r}.bam" \
      > "${s}_${r}_toolbox.log" 2>&1 )
  [[ -s "$OUT_DIR/$s/${s}_${r}_gft.bam" ]] || {
    log "ERROR: expected $OUT_DIR/$s/${s}_${r}_gft.bam — check ${s}_${r}_toolbox.log"; return 1; }
}
stage_align() { require STAR samtools; log "06 align"; for_each_sample align_one; }

# --- 07 Merge runs + region breakdown -----------------------------------------
merge_one() {
  local s="$1" r inputs=()
  for r in "${RUNS[@]}"; do inputs+=("$OUT_DIR/$s/${s}_${r}_gft.bam"); done
  # Intent: one BAM per sublibrary so cells sequenced across runs are counted once.
  run_named "07_merge_${s}" samtools merge -f "$OUT_DIR/$s/${s}_merged.bam" "${inputs[@]}"

  # Intent: tally the XF (locus function) tag exactly once per read, so
  # categories such as CODING and CODING,UTR do not overlap.
  samtools view "$OUT_DIR/$s/${s}_merged.bam" \
    | awk -v s="$s" '
        { f = "NO_XF"; for (i = 12; i <= NF; i++) if ($i ~ /^XF:Z:/) { f = substr($i, 6); break }
          n[f]++; tot++ }
        END { for (k in n) printf "%s\t%s\t%d\t%.4f\n", s, k, n[k], n[k] / tot
              printf "%s\tTOTAL\t%d\t1.0000\n", s, tot }' \
    | sort -k3,3nr > "$QC_DIR/${s}_region_counts.tsv"
}
stage_merge() {
  require samtools; log "07 merge"; for_each_sublib merge_one
  { echo -e "sublib\tlocus_function\treads\tfraction"; cat "$QC_DIR"/*_region_counts.tsv; } \
    > "$QC_DIR/region_counts.tsv"
}

# --- 08 Digital expression + cell-level QC -----------------------------------
dge_one() {
  local s="$1" d="$OUT_DIR/$s" tag="G${MIN_GENES_PER_CELL}"
  mkdir -p "$WORK_DIR/tmp_dge_$s"
  # Intent: genes × cells UMI count matrix for cells with >= MIN_GENES_PER_CELL genes.
  run_named "08_dge_${s}" DigitalExpression \
    INPUT="$d/${s}_merged.bam" OUTPUT="$d/${s}_${tag}_matrix.txt.gz" \
    SUMMARY="$d/${s}_${tag}_summary.txt" LOCUS_FUNCTION_LIST="$LOCUS_FUNCTION_LIST" \
    READ_MQ="$READ_MQ" EDIT_DISTANCE="$EDIT_DISTANCE" \
    MIN_NUM_GENES_PER_CELL="$MIN_GENES_PER_CELL" TMP_DIR="$WORK_DIR/tmp_dge_$s"

  # Intent: reads-per-barcode histogram for a knee/elbow plot.
  run_named "08_elbow_${s}" BamTagHistogram I="$d/${s}_merged.bam" \
    O="$d/${s}_merged_elbow.tsv" FILTER_PCR_DUPLICATES=true READ_MQ="$READ_MQ" TAG=XC
}

summarise_dge() {
  # Intent: per-sublibrary cells, genic reads, UMIs and reads-per-UMI. Summary
  # columns: CELL_BARCODE NUM_GENIC_READS NUM_TRANSCRIPTS NUM_GENES. Header and
  # comment lines are skipped by content.
  local s tag="G${MIN_GENES_PER_CELL}"
  echo -e "sublib\tcells\tgenic_reads\tumis\treads_per_umi"
  for s in "${SUBLIBS[@]}"; do
    awk -v s="$s" -v g="$UMI_STATS_MIN_GENES" '
      $1 ~ /^#/ || $1 == "CELL_BARCODE" || NF < 4 { next }
      { cells++ } $4 > g { reads += $2; umis += $3 }
      END { printf "%s\t%d\t%d\t%d\t%.2f\n", s, cells, reads, umis, (umis ? reads / umis : 0) }
    ' "$OUT_DIR/$s/${s}_${tag}_summary.txt"
  done
}

stage_dge() {
  require DigitalExpression BamTagHistogram
  log "08 dge"; for_each_sublib dge_one
  summarise_dge > "$QC_DIR/dge_summary.tsv"
  column -t "$QC_DIR/dge_summary.tsv" >&2
}

# --- Driver ------------------------------------------------------------------
STAGES=("${@:-align merge dge}")
for st in ${STAGES[*]}; do "stage_$st"; done
log "02_align_merge_dge done"
