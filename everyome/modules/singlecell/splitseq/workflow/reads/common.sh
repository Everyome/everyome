#!/usr/bin/env bash
# Shared helpers for the read-processing stages. Sourced, not executed.

set -euo pipefail

# Resolve repo root (two levels up from this file) and load the config.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_FILE="${CONFIG_FILE:-$REPO_ROOT/config/reads.env}"
# shellcheck source=/dev/null
source "$CONFIG_FILE"
cd "$REPO_ROOT"

[[ -n "${JAVA_HOME_OVERRIDE:-}" ]] && export JAVA_HOME="$JAVA_HOME_OVERRIDE"

# Timestamped log line on stderr.
log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*" >&2; }

# Fail early with a clear message if a required tool is missing.
require() {
  local tool
  for tool in "$@"; do
    command -v "$tool" >/dev/null 2>&1 || { log "ERROR: '$tool' not found on PATH"; exit 1; }
  done
}

# Run a command with argv[0] set to [<prefix>_]<user>_<tag> so it is identifiable in ps/top; the prefix comes
# from EVERYOME_JOB_PREFIX, as for job names. (Interpreter-launched tools may still show the interpreter name.)
run_named() {
  local tag="$1"; shift
  ( exec -a "${EVERYOME_JOB_PREFIX:+${EVERYOME_JOB_PREFIX}_}${PIPELINE_USER}_${tag}" "$@" )
}

# Run a function for every sublibrary × run, at most MAX_PARALLEL at a time,
# and fail if any job failed.
for_each_sample() {
  local fn="$1" sublib run pids=() failed=0
  for sublib in "${SUBLIBS[@]}"; do
    for run in "${RUNS[@]}"; do
      "$fn" "$sublib" "$run" &
      pids+=("$!")
      while (( $(jobs -rp | wc -l) >= MAX_PARALLEL )); do sleep 1; done
    done
  done
  for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
  (( failed == 0 )) || { log "ERROR: at least one '$fn' job failed"; exit 1; }
}

# Same, but once per sublibrary.
for_each_sublib() {
  local fn="$1" sublib pids=() failed=0
  for sublib in "${SUBLIBS[@]}"; do
    "$fn" "$sublib" &
    pids+=("$!")
  done
  for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
  (( failed == 0 )) || { log "ERROR: at least one '$fn' job failed"; exit 1; }
}
