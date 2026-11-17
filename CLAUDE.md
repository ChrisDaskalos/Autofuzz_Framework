# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Two things live together here:

1. **STM32F103 servo firmware** (`Core/`, `Drivers/`, `ServoProject.ioc`): receives commands over UART (DMA + idle-line callback in `main.c`), runs a password → menu → servo-command state machine (`Core/Src/protocol.c`), and ramps a PWM servo (`Core/Src/servo.c`). Built only in **STM32CubeIDE** — the Makefiles here do not build firmware. `.project`/`.cproject` are not tracked; import via the `.ioc`.
2. **AutoFuzz** (MSc thesis tool): the Python package `autofuzz/` (command `autofuzz` = `python3 -m autofuzz`) reads a project's `autofuzz.yaml`, uses libclang to write CMocka edge tests and libFuzzer harnesses for its C functions, compiles them with clang + ASan/UBSan and runs them on the PC. `Tests/` holds the thesis example plus hand-written fuzzers and unit tests.

## Roadmap

Work follows [docs/ROADMAP.md](docs/ROADMAP.md) (AutoFuzz 1.0, milestones M2–M6). When asked to "do the next milestone": branch from the previous milestone branch, show the plan and wait for approval, one commit per step, `make test` after each step, never push, tick the checklist in ROADMAP.md, end with a summary in very simple English. Never touch the `thesis-v1` tag or the branches `master`, `test`, `backup-nov2026`.

## Commands (run from repo root)

```bash
make deps        # = autofuzz check: clang, CMocka, sanitizer/libFuzzer runtimes, libclang, PyYAML (prints install commands)
make build       # unit tests + `autofuzz build` (legacy config) + manual fuzzers
make test        # unit + `autofuzz run --fresh` for legacy, self-test and real configs (edge + 10 s fuzz) + manual fuzz + check-determinism, then Tests/check_results.py (~4 min)
make check-determinism   # `autofuzz generate` twice, diff -r
make fuzz        # longer fuzzing, FUZZ_MAX_SECS each (default 60)
make clean
docker build -t autofuzz . && docker run --rm autofuzz   # same as make test, in Ubuntu 24.04 + clang 18
docker build -f Dockerfile.ubuntu20 -t autofuzz:ubuntu20 .   # Ubuntu 20.04, Python 3.8, clang 10
python3 -m autofuzz run [--config Tests/legacy_thesis/autofuzz.yaml] [--only edge|fuzz] [--fuzz-seconds N] [--fresh]   # default: ./autofuzz.yaml = real Core/Src
```

Python deps: `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt` (libclang, PyYAML). The Makefiles run the tool with `PYTHONPATH=<repo>`, so `pip install .` is optional. Must stay compatible with **Python 3.8** (no `list[int]` hints, no `match`, no `importlib.resources.files`); the developer VM is Ubuntu 20.04 + clang 10.

Running a subset:
- `make -C Tests/legacy_thesis unit|edge|fuzz` (each requires `make build` first).
- A single unit test: `cd Tests/legacy_thesis && ./test_protocol_checksum.elf`.
- A single edge test: `cd Tests/legacy_thesis/autofuzz-out && ./bin/deterministic_edge_<Function>`.
- A single fuzzer: `cd Tests/legacy_thesis/autofuzz-out && ./bin/random_fuzz_<Function> -max_total_time=10 corpus/random_fuzz_<Function>`.
- A single manual fuzzer: `make -C Tests/fuzz_manual run-fuzz_protocol_cmd FUZZ_MAX_SECS=30` (output in `Tests/fuzz_manual/out/`).
- Reproduce a crash: run the fuzzer binary with the crash file as its only argument.

## "Passing" means findings match the expected list

The tests **intentionally fail** — they detect known bugs (thesis results). `make test` succeeds (exit 0, last line `All results as expected`) only when the set of findings exactly matches `Tests/expected_findings.txt`: every non-`maybe` line found, nothing new. `Tests/check_results.py` parses `Tests/results/*.log` and `Tests/fuzz_manual/out/*.log`, normalizing sanitizer `SUMMARY:` lines and CMocka `[  FAILED  ]` lines into `<stage> <program> <finding>` entries matched by regex.

Consequences:
- Fixing a bug (or changing line numbers in `test_common.c` / `protocol.c` / `servo.c`) requires updating `Tests/expected_findings.txt` — entries reference `test_common.c:162`, `protocol.c:159` and `servo.c:40`.
- `Tests/legacy_thesis/Makefile`'s own `test` target and `make fuzz` exit 1 by design.
- See `docs/FINDINGS.md` for the bug list, which findings are real firmware bugs vs. legacy-copy only, and why four hand-written unit tests fail. Keep it in sync when findings change.

## Architecture of the test side

User-facing docs: `docs/ARCHITECTURE.md` (flow diagram, commands, folder map), `docs/HOW_IT_WORKS.md` (worked example + glossary, quotes real log output), `docs/FINDINGS.md`, `docs/CONFIG.md` (every YAML key), `docs/INSTALL.md`. README.md is intentionally short and links to these.

- **`autofuzz/`** (the tool). `__main__.py` (CLI: init/check/generate/build/run/clean) → `config.py` (loads `autofuzz.yaml` merged over `defaults.yaml`; strict schema, unknown key = error; paths relative to the YAML; `fake_include_dirs` go before `include_dirs`, `builtin:<name>` = `autofuzz/fakes/<name>/`) → `main.py:generate()` → `scanner.py` (libclang: non-static functions defined in each `sources` file; edge values per type plus literals/comparisons/switch cases; `limits.int_ranges`; `skip_reason()` skips inline asm, int-constant-to-pointer casts, endless loops → `gen/skipped.txt`) → `generator.py` (caps to `limits.edge_cap`; writes `deterministic_edge_<fn>.c` and `random_fuzz_<fn>.c` into `<output_dir>/gen`; non-const `char *` gets a writable copy; pointer params without setup get NULL and an `AUTOFUZZ-NULL-ARGS` comment) → `stubgen.py` (stubs for functions/globals used but not defined, not from system headers → `<output_dir>/stubs/stubs.c`; warns on pointer-returning stubs) → `runner.py` (checks tools and prints install commands; compiles with clang via subprocess; runs; logs to `<output_dir>/logs/{edge,fuzz}.log`) → `review.py` (writes `AUTOFUZZ: NEEDS REVIEW (<reason>): <report line>` when the top frame is in gen/stubs/fakes/rt or a NULL crash hit a NULL argument). **Nothing project-specific may be in the Python code** — headers come from `harness.includes`, struct preparation from `harness.setup`, test strings from `limits.string_seeds`, HAL types from fake headers. Output must stay deterministic (sorted, no timestamps).
- **Root `autofuzz.yaml`** tests the **real** `Core/Src/protocol.c` and `servo.c`, compiled **without** `UNIT_TEST`, with `builtin:stm32f1_hal` and generated stubs. Output in `./autofuzz-out/`. `main.c` is not covered (needs registers; also does not compile on PC: `dmaBuffer[64]` in `main.h` vs `[1024]`, see `docs/FINDINGS.md`).
- **`Tests/autofuzz_selftest/`** tiny C project that proves skip detection, stubs (incl. pointer-return warning) and needs-review (NULL argument, fake-header frame). `Tests/run_suite.sh <cfg> <prefix>` runs one config for `make test` and copies logs to `Tests/results/<prefix>{edge,fuzz}.log`, `<prefix>skipped.txt`. `check_results.py` `SUITES`: legacy (`edge`/`fuzz`), `self-*`, `real-*`, plus stage `skipped`; findings also `ASSERT <file>:<line> in <fn>` and `REVIEW (<reason>) <finding>`.

- **`Tests/legacy_thesis/`** (the thesis example, formerly `Tests/unit_tests`) tests a **PC copy** of the firmware logic in `test_common.c/.h` (with fake HAL), not `Core/Src` directly (the root `autofuzz.yaml` does that). It also has its own `protocol_defs.h`/`servo_defs.h` that differ slightly from `Core/Inc`. Keep this in mind when a change to the firmware should also be mirrored in the copy (or vice versa).
  - `Tests/legacy_thesis/autofuzz.yaml` points AutoFuzz at `test_common.c` and holds the servo-specific seeds and the `ProtocolContext` setup. Its output goes to `Tests/legacy_thesis/autofuzz-out/`; the root `make test` copies the edge/fuzz logs to `Tests/results/`.
  - `Tests/legacy_thesis/Makefile` builds only the hand-written CMocka tests (`test_*.c` except `test_common.c` → `test_*.elf`); its `edge`/`fuzz` targets call `autofuzz run --only ...`.
  - `autofuzz-out/`, binaries, `build/`, `Tests/results/` are gitignored — never commit them.
- **`Tests/fuzz_manual/`** hand-written libFuzzer harnesses that link the **real** `Core/Src/protocol.c` and `servo.c` compiled with `-DUNIT_TEST -DFUZZING -DSTRICT_HAL_STUBS`. Firmware sources switch includes on `#ifdef UNIT_TEST` to pull in `Tests/fuzz_manual/test_common.h` (HAL stubs — distinct from the legacy_thesis one). `fuzz_uart_dma.c` is a copy of the DMA idle-callback logic from `main.c`; its fake DMA counter is limited to 0..`DMA_BUFFER_SIZE` (1024) to match hardware. `fuzz_custom_mutator.c` is linked into all harnesses. `corpus/` is committed read-only seeds; new inputs go to `work_corpus/`. `mock_protocol_multi.c` is not built.
- **CI** (`.github/workflows/unit-and-fuzz.yml`): native Ubuntu 24.04 job, Docker job, and `ubuntu20` job (`Dockerfile.ubuntu20`: Python 3.8 + clang 10) all run `make test`; manual dispatch adds a long `make fuzz`.

## Firmware conventions

- CubeMX-generated files: put hand edits only inside `/* USER CODE BEGIN ... */ ... /* USER CODE END ... */` blocks, or CubeMX regeneration will drop them.
- The `#ifdef UNIT_TEST` include switches at the top of `Core/Src/protocol.c`, `servo.c`, `main.c` are what make the firmware PC-testable; preserve them.
- Makefiles use `.RECIPEPREFIX := >` — recipe lines start with `>`, not tabs.
