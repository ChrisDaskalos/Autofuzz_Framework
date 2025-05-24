# ─────────── build settings ───────────
TARGETS      = fuzz_protocol_session fuzz_protocol_cmd fuzz_uart_dma
SEED_CORPUS  = fuzz_corpus
CORE_INC     = /home/fretz/STM32CubeIDE/workspace_1.17.0/ServoProject/Core/Inc
CORE_SRC     = ../../Core/Src/protocol.c ../../Core/Src/servo.c

COMMON_FLAGS = -O1 -g \
               -fsanitize=fuzzer,address,undefined,bounds,integer \
               -DFUZZING -DFUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION \
               -DSTRICT_HAL_STUBS -DUNIT_TEST -DFUZZING
CFLAGS  = -I$(CORE_INC) -I. $(COMMON_FLAGS)
LDFLAGS = -fsanitize=fuzzer,address,undefined

# ─────────── build rules ──────────────
fuzz_protocol_session: fuzz_protocol_session.c test_common.c \
                       fuzz_custom_mutator.c $(CORE_SRC)
	clang $(CFLAGS) $^ -o $@ $(LDFLAGS)

fuzz_protocol_cmd:     fuzz_protocol_cmd.c  test_common.c \
                       fuzz_custom_mutator.c $(CORE_SRC)
	clang $(CFLAGS) $^ -o $@ $(LDFLAGS)

fuzz_uart_dma:         fuzz_uart_dma.c  test_common.c \
                       fuzz_custom_mutator.c $(CORE_SRC)
	clang $(CFLAGS) $^ -o $@ $(LDFLAGS)

# ─────────── sanitizer logs ───────────
export ASAN_OPTIONS  = halt_on_error=0:log_path=fuzz_out/asan
export UBSAN_OPTIONS = halt_on_error=0:log_path=fuzz_out/ubsan:print_stacktrace=1

# ─────────── run helpers ──────────────
.PHONY: run-session run-onecmd run-dma run clean

run-session: fuzz_protocol_session
	@mkdir -p fuzz_out
	@echo "=== session harness (10 min) ==="
	ASAN_OPTIONS=$(ASAN_OPTIONS) \
	UBSAN_OPTIONS=$(UBSAN_OPTIONS) \
	./fuzz_protocol_session $(SEED_CORPUS) fuzz_out \
	  -dict=protocol.dict \
	  -use_value_profile=1 -use_counters=1 \
	  -ignore_crashes=1 -max_len=16384 \
	  -max_total_time=600 -timeout=10

run-onecmd: fuzz_protocol_cmd
	@mkdir -p fuzz_out
	@echo "=== one-command harness (10 min) ==="
	ASAN_OPTIONS=$(ASAN_OPTIONS) \
	UBSAN_OPTIONS=$(UBSAN_OPTIONS) \
	./fuzz_protocol_cmd $(SEED_CORPUS) fuzz_out \
	  -dict=fuzz_cmd.dict \
	  -use_value_profile=1 -use_cmp=1 \
	  -ignore_crashes=1 -max_len=64 \
	  -max_total_time=3600 -timeout=10 \
	  

run-dma: fuzz_uart_dma
	@mkdir -p fuzz_out
	@echo "=== UART-DMA harness (10 min) ==="
	ASAN_OPTIONS=$(ASAN_OPTIONS) \
	UBSAN_OPTIONS=$(UBSAN_OPTIONS) \
	./fuzz_uart_dma $(SEED_CORPUS) fuzz_out \
	  -dict=fuzz_dma.dict \
	  -use_value_profile=1 -use_cmp=1 \
	  -ignore_crashes=1 -max_len=128 \
	  -max_total_time=600 -timeout=10

# default
run: run-session

clean:
	rm -f $(TARGETS) *.profraw *.profdata fuzz_out/asan* fuzz_out/ubsan*
