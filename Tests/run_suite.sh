#!/bin/sh
# Run one AutoFuzz config for `make test` and copy its logs to Tests/results/.
#
#   Tests/run_suite.sh <autofuzz.yaml> <prefix> [more autofuzz run options]
#
# Writes Tests/results/<prefix>autofuzz.log, <prefix>edge.log, <prefix>fuzz.log
# and <prefix>skipped.txt. The config must use output_dir: autofuzz-out.
# Exit code: 0, or the exit code of autofuzz if it is 2 or more (a real error;
# 1 only means "found something", which check_results.py judges).
# Uses AUTOFUZZ from the environment (set by the Makefile).
cfg="$1"; prefix="$2"; shift 2
results=Tests/results
out="$(dirname "$cfg")/autofuzz-out"
env $AUTOFUZZ run --config "$cfg" --fresh "$@" > "$results/${prefix}autofuzz.log" 2>&1
rc=$?
label="${prefix%-}"
grep -E '^=== (EDGE|FUZZ)|^ +SUMMARY|SKIPPED|WARNING|NEEDS REVIEW|^>>> Report|^    F[0-9]+ ' "$results/${prefix}autofuzz.log" | sed "s|^|[$label] |"
if [ $rc -ge 2 ]; then
    cat "$results/${prefix}autofuzz.log"
    exit $rc
fi
cp "$out/logs/edge.log" "$results/${prefix}edge.log"
cp "$out/logs/fuzz.log" "$results/${prefix}fuzz.log"
if [ -f "$out/gen/skipped.txt" ]; then cp "$out/gen/skipped.txt" "$results/${prefix}skipped.txt"; fi
exit 0
