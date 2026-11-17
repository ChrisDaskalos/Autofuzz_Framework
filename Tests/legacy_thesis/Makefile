## Tests/legacy_thesis - the thesis example (tests the PC copy test_common.c)
##
##   make build   compile the hand-written CMocka tests (test_*.c)
##   make unit    run them
##   make edge    autofuzz: generate, compile and run the edge tests
##   make fuzz    autofuzz: the same for the fuzzers (FUZZ_MAX_SECS each)
##   make test    unit + edge + fuzz, with a summary (exits 1 today, see below)
##   make clean
##
## The generated tests are made by AutoFuzz from autofuzz.yaml in this
## folder; they go to autofuzz-out/. The usual entry point is the root
## Makefile (`make test`), which compares the findings with the expected list.
.RECIPEPREFIX := >

CC := clang
REPO := $(abspath ../..)
AUTOFUZZ := cd $(REPO) && PYTHONPATH=$(REPO) python3 -m autofuzz
CONFIG := Tests/legacy_thesis/autofuzz.yaml

# Same flags as AutoFuzz uses for the edge tests
CFLAGS := -Wall -Wextra -g -O0 -fno-omit-frame-pointer -std=c11 \
          -DUNIT_TEST -D_POSIX_C_SOURCE=200809L -I. -I../../Core/Inc \
          -fsanitize=address,undefined -fno-sanitize-recover=address
LDLIBS := -lcmocka

STUB_SRC := test_common.c
STUB_OBJ := build/unit/test_common.o
MANUAL_TESTS := $(filter-out $(STUB_SRC),$(wildcard test_*.c))
MANUAL_TEST_BIN := $(MANUAL_TESTS:%.c=%.elf)
FUZZ_MAX_SECS ?= 10

.PHONY: all help build unit edge fuzz test clean
.DELETE_ON_ERROR:

all: build

help:
> @sed -n 's/^##//p' Makefile

$(STUB_OBJ): $(STUB_SRC) test_common.h protocol.h protocol_defs.h servo_defs.h
> @mkdir -p $(dir $@)
> @echo "  CC (unit)  $<"
> @$(CC) $(CFLAGS) -c $< -o $@

%.elf: %.c $(STUB_OBJ)
> @echo "  LD (unit)  $@"
> @$(CC) $(CFLAGS) $< $(STUB_OBJ) $(LDLIBS) -o $@

build: $(MANUAL_TEST_BIN)

# Run the hand-written unit tests
unit: $(MANUAL_TEST_BIN)
> @echo ">>> Running manual unit tests..."
> @rc=0; \
> for exe in $(MANUAL_TEST_BIN); do \
>   echo ""; \
>   echo "=== TEST: $$exe ==="; \
>   CMOCKA_MESSAGE_OUTPUT=STDOUT CMOCKA_COLOR=on \
>   ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 \
>   UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1:report_error_type=1 \
>   "./$$exe" || rc=$$?; \
> done; \
> echo ""; \
> if [ $$rc -eq 0 ]; then echo ">>> All manual tests passed!"; else echo ">>> Some tests failed!"; fi; \
> exit $$rc

edge:
> @$(AUTOFUZZ) run --config $(CONFIG) --only edge

fuzz:
> @$(AUTOFUZZ) run --config $(CONFIG) --only fuzz --fuzz-seconds $(FUZZ_MAX_SECS)

# Every stage runs even if an earlier one fails, then a summary is printed.
# Today all of them report findings on purpose (see docs/FINDINGS.md),
# so this exits 1.
test: build
> @u=PASS; a=PASS; \
> $(MAKE) --no-print-directory unit || u=FAIL; \
> $(AUTOFUZZ) run --config $(CONFIG) --fuzz-seconds $(FUZZ_MAX_SECS) || a=FAIL; \
> echo ""; \
> echo "================ SUMMARY (Tests/legacy_thesis) ================"; \
> echo "  unit             : $$u"; \
> echo "  autofuzz edge+fuzz: $$a"; \
> echo "  Known findings make both FAIL today."; \
> echo "  See docs/FINDINGS.md before you worry."; \
> echo "============================================================"; \
> [ "$$u$$a" = "PASSPASS" ]

clean:
> @echo ">>> Cleaning build artifacts..."
> @rm -f $(MANUAL_TEST_BIN)
> @rm -rf build
> @$(AUTOFUZZ) clean --config $(CONFIG) >/dev/null
> @echo ">>> Clean complete!"
