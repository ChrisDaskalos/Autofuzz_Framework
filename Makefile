## AutoFuzz - top-level commands. Run from the repository root.
##
##   make deps    check that the needed tools are installed
##   make build   unit tests + `autofuzz build` + hand-written fuzzers
##   make test    unit + edge + short fuzzing, compared with the expected
##                findings (about 3 minutes; exit 0 = as expected)
##   make check-determinism  generate twice, the outputs must be identical
##   make fuzz    longer fuzzing of all fuzzers (FUZZ_MAX_SECS each)
##   make clean   remove everything that build/test/fuzz created
##
## This Makefile is only for the PC tests. The STM32 firmware itself is
## built in STM32CubeIDE (see docs/ARCHITECTURE.md).
.RECIPEPREFIX := >

UNIT   := Tests/legacy_thesis
MANUAL := Tests/fuzz_manual
RESULTS := Tests/results

# Seconds per fuzzer for `make fuzz` and for `make test`
FUZZ_MAX_SECS  ?= 60
TEST_FUZZ_SECS ?= 10

PYTHON ?= python3
# The tool is run from the repository root, so `pip install .` is not needed.
AUTOFUZZ := PYTHONPATH=$(CURDIR) $(PYTHON) -m autofuzz
LEGACY_CFG := $(UNIT)/autofuzz.yaml
SELF_CFG   := Tests/autofuzz_selftest/autofuzz.yaml
# The real firmware sources (Core/Src/protocol.c, servo.c)
REAL_CFG   := autofuzz.yaml
# Every config that `make test` runs and checks for determinism
CONFIGS    := $(LEGACY_CFG) $(SELF_CFG) $(REAL_CFG)
export AUTOFUZZ

.PHONY: help deps build test fuzz clean check-determinism

help:
> @sed -n 's/^##//p' $(firstword $(MAKEFILE_LIST))

# Checks clang, CMocka, the sanitizer and libFuzzer runtimes, PyYAML and
# libclang. Prints the exact install command for anything that is missing.
deps:
> @command -v make >/dev/null || { echo "MISSING: make (sudo apt install make)"; exit 1; }
> @command -v $(PYTHON) >/dev/null || { echo "MISSING: $(PYTHON) (sudo apt install python3)"; exit 1; }
> @$(AUTOFUZZ) check --config $(LEGACY_CFG)

# Hand-written unit tests, then `autofuzz build`, then the hand-written fuzzers.
build: deps
> $(MAKE) -C $(UNIT) build
> $(AUTOFUZZ) build --config $(LEGACY_CFG)
> $(MAKE) -C $(MANUAL) build

# Every stage runs even if an earlier one fails. The output is saved in
# Tests/results/ and compared with Tests/expected_findings.txt.
# Exit code 0 = the findings are exactly the expected ones.
# Fuzz state from earlier runs is removed first (--fresh, out/, work_corpus/),
# so every run starts the same.
test: build
> @rm -rf $(RESULTS) $(MANUAL)/out $(MANUAL)/work_corpus
> @mkdir -p $(RESULTS)
> @$(MAKE) --no-print-directory -C $(UNIT) unit > $(RESULTS)/unit.log 2>&1; \
>  grep -E '^=== TEST|^\[  (PASSED|FAILED)  \] [0-9a-z]|^SUMMARY' $(RESULTS)/unit.log; true
> @Tests/run_suite.sh $(LEGACY_CFG) "" --fuzz-seconds $(TEST_FUZZ_SECS)
> @Tests/run_suite.sh $(SELF_CFG) self-
> @Tests/run_suite.sh $(REAL_CFG) real- --fuzz-seconds $(TEST_FUZZ_SECS)
> @$(MAKE) --no-print-directory -C $(MANUAL) fuzz FUZZ_MAX_SECS=$(TEST_FUZZ_SECS) > $(RESULTS)/manual.log 2>&1; \
>  grep -E '^=== MANUAL|^Done|^SUMMARY' $(RESULTS)/manual.log; true
> @$(MAKE) --no-print-directory check-determinism
> @$(PYTHON) Tests/check_results.py

# Same input, same output: generate twice with different Python hash seeds
# (so the order of a Python set cannot leak into the files) and compare.
check-determinism:
> @rm -rf $(RESULTS)/determinism
> @set -e; for cfg in $(CONFIGS); do \
>   d=$(RESULTS)/determinism/$$(dirname $$cfg | tr / _); \
>   PYTHONHASHSEED=1 $(AUTOFUZZ) generate --config $$cfg --output-dir $$d/a >/dev/null; \
>   PYTHONHASHSEED=2 $(AUTOFUZZ) generate --config $$cfg --output-dir $$d/b >/dev/null; \
>   diff -r $$d/a $$d/b; \
>   echo ">>> Determinism: $$cfg: generating twice gives identical files ($$(find $$d/a -type f | wc -l) files)"; \
> done
> @rm -rf $(RESULTS)/determinism

# Both fuzz suites always run; the exit code is 1 if either found something.
fuzz: build
> @rc=0; \
> $(AUTOFUZZ) run --config $(LEGACY_CFG) --only fuzz --fuzz-seconds $(FUZZ_MAX_SECS) || rc=1; \
> $(AUTOFUZZ) run --config $(REAL_CFG) --only fuzz --fuzz-seconds $(FUZZ_MAX_SECS) || rc=1; \
> $(MAKE) -C $(MANUAL) fuzz FUZZ_MAX_SECS=$(FUZZ_MAX_SECS) || rc=1; \
> echo ""; \
> echo ">>> Fuzzing done. Results: autofuzz-out/crashes/ autofuzz-out/logs/ $(UNIT)/autofuzz-out/crashes/ $(UNIT)/autofuzz-out/logs/ $(MANUAL)/out/"; \
> exit $$rc

clean:
> $(MAKE) -C $(UNIT) clean
> $(MAKE) -C $(MANUAL) clean
> @$(AUTOFUZZ) clean --config $(SELF_CFG) >/dev/null
> @$(AUTOFUZZ) clean --config $(REAL_CFG) >/dev/null
> rm -rf $(RESULTS)
