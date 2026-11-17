## Hand-written libFuzzer harnesses.
## Unlike Tests/legacy_thesis, these link the REAL firmware code
## (Core/Src/protocol.c and Core/Src/servo.c), compiled with -DUNIT_TEST.
##
## Targets: build | fuzz | clean
.RECIPEPREFIX := >

CC            = clang
FUZZ_MAX_SECS ?= 60

ROOT     := ../..
CORE_SRC := $(ROOT)/Core/Src/protocol.c $(ROOT)/Core/Src/servo.c

# Core/Inc first (firmware headers), then this folder (test_common.h).
CFLAGS  = -O1 -g -I$(ROOT)/Core/Inc -I. \
          -fsanitize=fuzzer,address,undefined,bounds,integer \
          -DUNIT_TEST -DFUZZING -DFUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION \
          -DSTRICT_HAL_STUBS
LDFLAGS = -fsanitize=fuzzer,address,undefined

HARNESSES := fuzz_protocol_session fuzz_protocol_cmd fuzz_uart_dma
BINS      := $(HARNESSES:%=bin/%)
COMMON    := test_common.c fuzz_custom_mutator.c $(CORE_SRC)

# Per-harness run options (dictionary + maximum input length)
OPTS_fuzz_protocol_session := -dict=protocol.dict -max_len=16384
OPTS_fuzz_protocol_cmd     := -dict=fuzz_cmd.dict -max_len=64
OPTS_fuzz_uart_dma         := -dict=fuzz_dma.dict -max_len=128

RUNS := $(HARNESSES:%=run-%)

.PHONY: build fuzz clean $(RUNS)

build: $(BINS)

bin/%: %.c $(COMMON) test_common.h
> @mkdir -p bin
> @echo "  CC (manual fuzz)  $*"
> @$(CC) $(CFLAGS) $< $(COMMON) -o $@ $(LDFLAGS)

# New interesting inputs go to work_corpus/ (ignored by git);
# corpus/ is the committed seed set and is only read.
# Every fuzzer runs even if an earlier one crashes; the result of each
# run is written to out/<name>.status and checked at the end.
# UBSan findings do not stop the fuzzer, so the logs are checked too.
fuzz: $(RUNS)
> @echo ""
> @ok=$$(cat $(HARNESSES:%=out/%.status) 2>/dev/null | grep -c '^0$$'); \
> if [ "$$ok" != "$(words $(HARNESSES))" ] || grep -q 'SUMMARY:' out/*.log; then \
>   echo ">>> Manual fuzzers found issues:"; \
>   grep -h 'SUMMARY:' out/*.log | sed 's/ (.*//' | sort | uniq -c; \
>   echo "    Logs: out/<name>.log   Crash inputs: out/<name>/"; \
>   exit 1; \
> else \
>   echo ">>> Manual fuzzers finished without findings"; \
> fi

$(RUNS): run-%: bin/%
> @mkdir -p out/$* work_corpus/$*
> @echo ""; echo "=== MANUAL FUZZ: $* ($(FUZZ_MAX_SECS)s) ==="
> @UBSAN_OPTIONS=print_stacktrace=1 \
>  ./bin/$* work_corpus/$* corpus $(OPTS_$*) \
>    -use_value_profile=1 -timeout=10 \
>    -artifact_prefix=out/$*/ \
>    -max_total_time=$(FUZZ_MAX_SECS) > out/$*.log 2>&1; \
>  echo $$? > out/$*.status; \
>  grep -E 'SUMMARY|^Done' out/$*.log || true

clean:
> rm -rf bin out work_corpus
