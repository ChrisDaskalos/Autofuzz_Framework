## AutoFuzz - top-level commands. Run from the repository root.
##
##   make deps    check that the needed tools are installed
##   make build   generate harnesses + compile all tests and fuzzers
##   make test    unit + edge + short fuzzing, compared with the expected
##                findings (about 3 minutes; exit 0 = as expected)
##   make fuzz    longer fuzzing of all fuzzers (FUZZ_MAX_SECS each)
##   make clean   remove everything that build/test/fuzz created
##
## This Makefile is only for the PC tests. The STM32 firmware itself is
## built in STM32CubeIDE (see README.md).
.RECIPEPREFIX := >

UNIT   := Tests/unit_tests
MANUAL := Tests/fuzz_manual
RESULTS := Tests/results

# Seconds per fuzzer for `make fuzz` and for `make test`
FUZZ_MAX_SECS  ?= 60
TEST_FUZZ_SECS ?= 10

PYTHON ?= python3

.PHONY: help deps build test fuzz clean

help:
> @sed -n 's/^##//p' $(firstword $(MAKEFILE_LIST))

deps:
> @ok=1; \
> command -v clang   >/dev/null || { echo "MISSING: clang (apt install clang)"; ok=0; }; \
> command -v make    >/dev/null || { echo "MISSING: make (apt install make)"; ok=0; }; \
> command -v $(PYTHON) >/dev/null || { echo "MISSING: $(PYTHON) (apt install python3)"; ok=0; }; \
> $(PYTHON) -c "import clang.cindex as c; c.Index.create()" 2>/dev/null \
>   || { echo "MISSING: Python libclang bindings (pip install -r requirements.txt)"; ok=0; }; \
> printf '#include <stdarg.h>\n#include <stddef.h>\n#include <setjmp.h>\n#include <cmocka.h>\nint main(void){return 0;}\n' \
>   | clang -x c - -lcmocka -o /dev/null 2>/dev/null \
>   || { echo "MISSING: CMocka (apt install libcmocka-dev)"; ok=0; }; \
> printf 'int LLVMFuzzerTestOneInput(const char*d,unsigned long n){return 0;}\n' \
>   | clang -x c - -fsanitize=fuzzer -o /dev/null 2>/dev/null \
>   || { echo "MISSING: libFuzzer support in clang (Ubuntu 24.04: apt install clang-18)"; ok=0; }; \
> if [ $$ok = 1 ]; then echo ">>> All dependencies found ($$(clang --version | head -1))"; \
> else echo ">>> Install the missing tools, or use Docker (see README.md)"; exit 1; fi

build: deps
> $(MAKE) -C $(UNIT) build
> $(MAKE) -C $(MANUAL) build

# Every stage runs even if an earlier one fails. The output is saved in
# Tests/results/ and compared with Tests/expected_findings.txt.
# Exit code 0 = the findings are exactly the expected ones.
# Fuzz state from earlier runs is removed first, so every run starts the same.
test: build
> @rm -rf $(RESULTS) $(UNIT)/lf_corpus $(UNIT)/crashes $(UNIT)/logs \
>        $(MANUAL)/out $(MANUAL)/work_corpus
> @mkdir -p $(RESULTS)
> @$(MAKE) --no-print-directory -C $(UNIT) unit > $(RESULTS)/unit.log 2>&1; \
>  grep -E '^=== TEST|^\[  (PASSED|FAILED)  \] [0-9a-z]|^SUMMARY' $(RESULTS)/unit.log; true
> @$(MAKE) --no-print-directory -C $(UNIT) edge > $(RESULTS)/edge.log 2>&1; \
>  grep -E '^=== EDGE|^\[  (PASSED|FAILED)  \] [0-9a-z]|^SUMMARY' $(RESULTS)/edge.log; true
> @$(MAKE) --no-print-directory -C $(UNIT) fuzz FUZZ_MAX_SECS=$(TEST_FUZZ_SECS) > $(RESULTS)/fuzz.log 2>&1; \
>  grep -E '^=== FUZZ|^Done|^SUMMARY' $(RESULTS)/fuzz.log; true
> @$(MAKE) --no-print-directory -C $(MANUAL) fuzz FUZZ_MAX_SECS=$(TEST_FUZZ_SECS) > $(RESULTS)/manual.log 2>&1; \
>  grep -E '^=== MANUAL|^Done|^SUMMARY' $(RESULTS)/manual.log; true
> @$(PYTHON) Tests/check_results.py

# Both fuzz suites always run; the exit code is 1 if either found something.
fuzz: build
> @rc=0; \
> $(MAKE) -C $(UNIT) fuzz FUZZ_MAX_SECS=$(FUZZ_MAX_SECS) || rc=1; \
> $(MAKE) -C $(MANUAL) fuzz FUZZ_MAX_SECS=$(FUZZ_MAX_SECS) || rc=1; \
> echo ""; \
> echo ">>> Fuzzing done. Results: $(UNIT)/crashes/ $(UNIT)/logs/ $(MANUAL)/out/"; \
> exit $$rc

clean:
> $(MAKE) -C $(UNIT) clean
> $(MAKE) -C $(MANUAL) clean
> rm -rf $(RESULTS)
