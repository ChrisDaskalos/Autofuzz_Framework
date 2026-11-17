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
> @$(AUTOFUZZ) run --config $(LEGACY_CFG) --fresh --fuzz-seconds $(TEST_FUZZ_SECS) > $(RESULTS)/autofuzz.log 2>&1; \
>  rc=$$?; grep -E '^=== (EDGE|FUZZ)|^ +SUMMARY|SKIPPED' $(RESULTS)/autofuzz.log; \
>  if [ $$rc -ge 2 ]; then cat $(RESULTS)/autofuzz.log; exit $$rc; fi; \
>  cp $(UNIT)/autofuzz-out/logs/edge.log $(UNIT)/autofuzz-out/logs/fuzz.log $(RESULTS)/
> @$(MAKE) --no-print-directory -C $(MANUAL) fuzz FUZZ_MAX_SECS=$(TEST_FUZZ_SECS) > $(RESULTS)/manual.log 2>&1; \
>  grep -E '^=== MANUAL|^Done|^SUMMARY' $(RESULTS)/manual.log; true
> @$(MAKE) --no-print-directory check-determinism
> @$(PYTHON) Tests/check_results.py

# Same input, same output: generate twice with different Python hash seeds
# (so the order of a Python set cannot leak into the files) and compare.
check-determinism:
> @rm -rf $(RESULTS)/determinism
> @PYTHONHASHSEED=1 $(AUTOFUZZ) generate --config $(LEGACY_CFG) --output-dir $(RESULTS)/determinism/a >/dev/null
> @PYTHONHASHSEED=2 $(AUTOFUZZ) generate --config $(LEGACY_CFG) --output-dir $(RESULTS)/determinism/b >/dev/null
> @diff -r $(RESULTS)/determinism/a/gen $(RESULTS)/determinism/b/gen \
>   && echo ">>> Determinism: generating twice gives identical files ($$(ls $(RESULTS)/determinism/a/gen | wc -l) files)"
> @rm -rf $(RESULTS)/determinism

# Both fuzz suites always run; the exit code is 1 if either found something.
fuzz: build
> @rc=0; \
> $(AUTOFUZZ) run --config $(LEGACY_CFG) --only fuzz --fuzz-seconds $(FUZZ_MAX_SECS) || rc=1; \
> $(MAKE) -C $(MANUAL) fuzz FUZZ_MAX_SECS=$(FUZZ_MAX_SECS) || rc=1; \
> echo ""; \
> echo ">>> Fuzzing done. Results: $(UNIT)/autofuzz-out/crashes/ $(UNIT)/autofuzz-out/logs/ $(MANUAL)/out/"; \
> exit $$rc

clean:
> $(MAKE) -C $(UNIT) clean
> $(MAKE) -C $(MANUAL) clean
> rm -rf $(RESULTS)
