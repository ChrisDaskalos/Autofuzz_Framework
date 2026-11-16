# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Two things live together here:

1. **STM32F103 servo firmware** (`Core/`, `Drivers/`, `ServoProject.ioc`): receives commands over UART (DMA + idle-line callback in `main.c`), runs a password → menu → servo-command state machine (`Core/Src/protocol.c`), and ramps a PWM servo (`Core/Src/servo.c`). Built only in **STM32CubeIDE** — the Makefiles here do not build firmware. `.project`/`.cproject` are not tracked; import via the `.ioc`.
2. **AutoFuzz** (MSc thesis tool, `Tests/`): a Python/libclang generator that writes CMocka edge tests and libFuzzer harnesses for C functions, plus hand-written fuzzers and unit tests, all built with clang + ASan/UBSan on the PC.

## Roadmap

Work follows [docs/ROADMAP.md](docs/ROADMAP.md) (AutoFuzz 1.0, milestones M2–M6). When asked to "do the next milestone": branch from the previous milestone branch, show the plan and wait for approval, one commit per step, `make test` after each step, never push, tick the checklist in ROADMAP.md, end with a summary in very simple English. Never touch the `thesis-v1` tag or the branches `master`, `test`, `backup-nov2026`.

## Commands (run from repo root)

```bash
make deps        # check clang, libFuzzer, CMocka, Python libclang
make build       # run AutoFuzz generator, then compile everything
make test        # unit + edge + short fuzz (TEST_FUZZ_SECS=10) + manual fuzz, then Tests/check_results.py (~3 min)
make fuzz        # longer fuzzing, FUZZ_MAX_SECS each (default 60)
make clean
docker build -t autofuzz . && docker run --rm autofuzz   # same as make test, in Ubuntu 24.04 + clang 18
```

Python deps: `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`.

Running a subset:
- `make -C Tests/legacy_thesis unit|edge|fuzz` (each requires `make build` first).
- A single unit test / edge test: `cd Tests/legacy_thesis && ./test_protocol_checksum.elf` or `./deterministic_edge_<Function>`.
- A single fuzzer: `cd Tests/legacy_thesis && ./random_fuzz_<Function> -max_total_time=10 ./lf_corpus`.
- A single manual fuzzer: `make -C Tests/fuzz_manual run-fuzz_protocol_cmd FUZZ_MAX_SECS=30` (output in `Tests/fuzz_manual/out/`).
- Reproduce a crash: run the fuzzer binary with the crash file as its only argument.

## "Passing" means findings match the expected list

The tests **intentionally fail** — they detect known bugs (thesis results). `make test` succeeds (exit 0, last line `All results as expected`) only when the set of findings exactly matches `Tests/expected_findings.txt`: every non-`maybe` line found, nothing new. `Tests/check_results.py` parses `Tests/results/*.log` and `Tests/fuzz_manual/out/*.log`, normalizing sanitizer `SUMMARY:` lines and CMocka `[  FAILED  ]` lines into `<stage> <program> <finding>` entries matched by regex.

Consequences:
- Fixing a bug (or changing line numbers in `test_common.c` / `protocol.c`) requires updating `Tests/expected_findings.txt` — entries reference `test_common.c:162` and `protocol.c:159`.
- `Tests/legacy_thesis/Makefile`'s own `test` target and `make fuzz` exit 1 by design.
- See README.md "Expected results" for the bug list and why four hand-written unit tests fail.

## Architecture of the test side

- **`Tests/legacy_thesis/`** tests a **PC copy** of the firmware logic in `test_common.c/.h` (with fake HAL), not `Core/Src` directly (`PROD_SRCS` is empty). It also has its own `protocol_defs.h`/`servo_defs.h` that differ slightly from `Core/Inc`. Keep this in mind when a change to the firmware should also be mirrored in the copy (or vice versa).
  - `autofuzz/main.py` → `scanner.py` (libclang: non-static functions with parameters; collects edge values from `config.py` per type plus literals/comparisons/switch cases in the source) → `generator.py` (caps to `EDGE_CAP`=12 values per parameter; writes `deterministic_edge_<fn>.c` and `random_fuzz_<fn>.c`). Output is deterministic. The file scanned is `STUB_SRC` (Makefile var).
  - Generation is stamped by `_autofuzz.stamp`; it reruns when `test_common.c` or the autofuzz Python files change.
  - `test_*.c` (excluding `test_common.c`) are hand-written CMocka tests, each built into `test_*.elf`.
  - Generated `.c` files, binaries, `build/`, `crashes/`, `lf_corpus/`, `logs/` are gitignored — never commit them.
- **`Tests/fuzz_manual/`** hand-written libFuzzer harnesses that link the **real** `Core/Src/protocol.c` and `servo.c` compiled with `-DUNIT_TEST -DFUZZING -DSTRICT_HAL_STUBS`. Firmware sources switch includes on `#ifdef UNIT_TEST` to pull in `Tests/fuzz_manual/test_common.h` (HAL stubs — distinct from the legacy_thesis one). `fuzz_uart_dma.c` is a copy of the DMA idle-callback logic from `main.c`; its fake DMA counter is limited to 0..`DMA_BUFFER_SIZE` (1024) to match hardware. `fuzz_custom_mutator.c` is linked into all harnesses. `corpus/` is committed read-only seeds; new inputs go to `work_corpus/`. `mock_protocol_multi.c` is not built.
- **CI** (`.github/workflows/unit-and-fuzz.yml`): native Ubuntu 24.04 job and Docker job both run `make test`; manual dispatch adds a long `make fuzz`.

## Firmware conventions

- CubeMX-generated files: put hand edits only inside `/* USER CODE BEGIN ... */ ... /* USER CODE END ... */` blocks, or CubeMX regeneration will drop them.
- The `#ifdef UNIT_TEST` include switches at the top of `Core/Src/protocol.c`, `servo.c`, `main.c` are what make the firmware PC-testable; preserve them.
- Makefiles use `.RECIPEPREFIX := >` — recipe lines start with `>`, not tabs.
