# ======================================================================
#  Unit-tests + AutoFuzz harnesses + LCOV coverage (compact workflow)
# ======================================================================

CC        := gcc
CFLAGS    := -Wall -Wextra -g -std=c11 -DUNIT_TEST -I. -I../../Core/Inc
LDFLAGS   := -lcmocka
COV_FLAGS := -O0 --coverage

# ---------- run-time limits (override from shell) ---------------------
FUZZ_MAX_SECS  ?= 30     # seconds per binary (0 = unlimited)
FUZZ_MAX_CASES ?= 500    # calls   per binary (0 = unlimited)

REPORT_DIR := cov_html
LCOV_INFO  := cov.info

# ----------------------------------------------------------------------
# 1) Hand-written CMocka suites
# ----------------------------------------------------------------------
TEST_SRC := \
  test_protocol_checksum.c \
  test_protocol_authentication.c \
  test_protocol_init.c \
  test_protocol_menu.c \
  test_protocol_servo_command.c \
  test_protocol_state_machine.c

TEST_ELF := $(TEST_SRC:.c=.elf)

# ----------------------------------------------------------------------
# 2) Stub code (coverage-instrumented)
#    – list every real function that harnesses might call
# ----------------------------------------------------------------------
STUB_SRC := \
    test_common.c 

STUB_OBJS := $(STUB_SRC:.c=.o)
export STUB_SRCS := $(STUB_SRC)      # read by autofuzz_scan.py

# ----------------------------------------------------------------------
# 3) Phony targets
# ----------------------------------------------------------------------
.PHONY: all clean fuzz test coverage

# ----------------------------------------------------------------------
# (a) Compile each stub source
# ----------------------------------------------------------------------
$(STUB_OBJS): %.o: %.c
	$(CC) $(CFLAGS) $(COV_FLAGS) -c $< -o $@

# ----------------------------------------------------------------------
# (b) Build each hand-written test binary
# ----------------------------------------------------------------------
%.elf: %.c $(STUB_OBJS)
	$(CC) $(CFLAGS) $(COV_FLAGS) $< $(STUB_OBJS) $(LDFLAGS) -o $@

# ----------------------------------------------------------------------
# (c) AutoFuzz – regenerate & compile harnesses
# ----------------------------------------------------------------------
# 1. stamp to (re)generate sources
_autofuzz.stamp: $(STUB_SRC) autofuzz/autofuzz_scan.py
	@echo ">>> (re)generating fuzz harnesses"
	@python3 autofuzz/autofuzz_scan.py
	@touch $@

# 2. build every fuzz_*.c that now exists
# build stubs first, then every harness
fuzz: _autofuzz.stamp $(STUB_OBJS)
	@for src in $(shell ls -1 fuzz_*.c 2>/dev/null); do \
	    exe=$${src%.c}; \
	    echo "  CC $$exe"; \
	    $(CC) $(CFLAGS) $(COV_FLAGS) $$src $(STUB_OBJS) $(LDFLAGS) -o $$exe; \
	done

# ----------------------------------------------------------------------
# (d) Build everything
# ----------------------------------------------------------------------
all: $(TEST_ELF) fuzz

# ----------------------------------------------------------------------
# (e) Run all executables and honour FUZZ_MAX_* limits
# ----------------------------------------------------------------------
test: all
	@rc=0; \
	for exe in test_*.elf fuzz_* ; do \
	  [ -x "$$exe" ] || continue; \
	  echo ">>> running $$exe"; \
	  FUZZ_MAX_SECS=$(FUZZ_MAX_SECS) FUZZ_MAX_CASES=$(FUZZ_MAX_CASES) \
	    ./$$exe || rc=$$?; \
	done; \
	echo "Test phase finished with rc=$$rc"; \
	exit $$rc

# ----------------------------------------------------------------------
# (f) Coverage report
# ----------------------------------------------------------------------
coverage:
	@$(MAKE) --no-print-directory -k test || true; \
	lcov   --quiet --capture --directory . -o $(LCOV_INFO); \
	genhtml --quiet --title "ServoProject coverage" \
	        $(LCOV_INFO) -o $(REPORT_DIR); \
	lcov   --summary $(LCOV_INFO) | grep -E "lines|functions"; \
	echo "Combined report → $(REPORT_DIR)/index.html"

# ----------------------------------------------------------------------
# (g) Clean
# ----------------------------------------------------------------------
clean:
	$(RM) -rf *.o *.elf fuzz_* _autofuzz.stamp $(LCOV_INFO) *.gc* $(REPORT_DIR)
