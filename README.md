# AutoFuzz: automatic edge tests and fuzzing for STM32 servo firmware

AutoFuzz is the tool from my MSc thesis. It reads C code with **libclang**,
finds the functions, and writes two kinds of tests for each function:

1. **Edge tests** (`deterministic_edge_*.c`): CMocka tests that call the
   function with boundary values (`INT_MIN`, `INT_MAX`, empty string,
   strings longer than the 1024-byte DMA buffer, ...).
2. **Fuzz harnesses** (`random_fuzz_*.c`): libFuzzer programs that call the
   function with random inputs.

Everything is compiled with AddressSanitizer and UndefinedBehaviorSanitizer,
so memory errors and integer overflows are reported with a file and line.

The example target is firmware for an STM32F103 that moves a servo motor
using commands it receives over UART.

---

## Quick start

You need either **Docker**, or **Linux with clang, CMocka and Python 3**.

### With Docker (easiest)

```bash
docker build -t autofuzz .     # installs everything and compiles (one time)
docker run --rm autofuzz       # runs `make test` (about 3 minutes)
```

Longer fuzzing: `docker run --rm autofuzz make fuzz FUZZ_MAX_SECS=300`

### Without Docker (Ubuntu 24.04)

```bash
sudo apt install clang-18 libclang-rt-18-dev build-essential libcmocka-dev python3-venv
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

make deps      # checks that everything is installed
make build     # generates the harnesses and compiles all tests
make test      # runs all tests and prints a summary
```

If `clang` is not found, either install the `clang` package or use
`sudo ln -s /usr/bin/clang-18 /usr/local/bin/clang`.

---

## Commands

Run these from the repository root.

| Command | What it does | Time |
|---|---|---|
| `make deps` | Checks clang, libFuzzer, CMocka, Python libclang. Tells you what is missing. | 1 s |
| `make build` | Runs AutoFuzz (writes the harnesses), then compiles all tests and fuzzers. | ~30 s |
| `make test` | Unit tests + edge tests + 10 s per fuzzer, then a summary. | ~3 min |
| `make fuzz` | Every fuzzer for `FUZZ_MAX_SECS` seconds (default 60). | ~13 min |
| `make clean` | Deletes everything that the commands above created. | 1 s |

Change the times: `make fuzz FUZZ_MAX_SECS=600`, `make test TEST_FUZZ_SECS=30`.

---

## Expected results

**Today `make test` ends with an error. This is correct:** the tests find
known bugs, and these bugs are the results of the thesis. The summary at
the end shows what was found and what was expected:

```
========================= SUMMARY =========================
  unit tests (hand-written)      : FAIL   expected: FAIL
  edge tests (AutoFuzz)          : FAIL   expected: FAIL
  fuzz (AutoFuzz harnesses)      : FAIL   expected: FAIL
  fuzz (Tests/fuzz_manual)       : FAIL   expected: FAIL
```

If a line says `PASS`, a known bug has gone away. Then update this section.

### Bugs found (thesis results)

| # | Bug | Where | Found by |
|---|---|---|---|
| 1 | **Stack buffer overflow.** A command with 1024 or more characters and no line end fills the 1024-byte buffer with no `\0` at the end. Then `strtok`/`strrchr` read past the end of the buffer. | `Protocol_ProcessCommand` in `Tests/unit_tests/test_common.c` | `deterministic_edge_Protocol_ProcessCommand` |
| 2 | **Signed integer overflow** in the checksum: `angle + step` with large numbers (for example `INT_MAX + 1`) is undefined behaviour in C. | `ComputeChecksumFromNumbers`: `Tests/unit_tests/test_common.c:162` and real firmware `Core/Src/protocol.c:159` | edge test, `random_fuzz_ComputeChecksumFromNumbers` (crashes in < 1 s), `test_manual_overflow`, `Tests/fuzz_manual` |
| 3 | **DMA length not checked.** If the DMA counter says more bytes than the buffer holds, `memcpy` copies past the buffer, and `DMA_BUFFER_SIZE - remain` wraps around. | `HAL_UART_IdleCallback` / `ProcessUartData` (copy of `Core/Src/main.c`) | `Tests/fuzz_manual` `fuzz_uart_dma` |

### Unit tests that fail (and why)

The hand-written unit tests in `Tests/unit_tests/test_*.c` describe how the
protocol **should** behave. Four of them fail because the code does
something else. The real firmware (`Core/Src/protocol.c`) behaves the same
way as the test copy.

| Test | Input | Test expects | Code does |
|---|---|---|---|
| `test_state_machine_cancellation_with_whitespace` | `"   B   "` while the servo moves | cancel | Ignores it. Only exactly `B` or `b` cancels; spaces are not removed. |
| `test_servo_command_extra_fields` | `90,5,95,100` | reject | Accepts it. Only the first 3 fields are read; the 4th is ignored. |
| `test_servo_command_zero_step` | `90,0,90` | reject | Accepts it. There is no check for step = 0. On the real board `Servo_Ramp` then hits `assert(step != 0 ...)` and the firmware stops. |
| `test_servo_command_negative_step` | `90,-5,85` | reject | Accepts it. `-5` becomes `251` (stored as `uint8_t`) and the checksum still matches. On the real board this also hits the `assert` in `Servo_Ramp`. |

`test_manual_overflow` also "fails" on purpose: it is a small demo of bug 2.

---

## Folder map

```
Core/, Drivers/              STM32 firmware (CubeMX project, HAL library)
ServoProject.ioc             CubeMX project file
Makefile                     the commands above (PC tests only)
Dockerfile                   Ubuntu 24.04 + clang 18 test environment
requirements.txt             Python package for AutoFuzz (libclang)

Tests/unit_tests/            AutoFuzz + tests on a PC copy of the logic
  autofuzz/                  the AutoFuzz tool (Python)
    main.py                  entry point: parse, find functions, write files
    scanner.py               finds functions and edge values with libclang
    generator.py             writes deterministic_edge_*.c and random_fuzz_*.c
    config.py                edge values and string seeds  <- edit for your project
  test_common.c/.h           PC copy of the protocol + servo logic, fake HAL
  test_*.c                   hand-written CMocka unit tests
  Makefile                   build | unit | edge | fuzz | test | clean

Tests/fuzz_manual/           hand-written libFuzzer harnesses that link the
                             REAL firmware (Core/Src/protocol.c, servo.c)
                             -> see Tests/fuzz_manual/README.md
```

Files created by `make` (generated harnesses, binaries, `build/`, `logs/`,
`crashes/`, `lf_corpus/`, `out/`) are not in git. `make build` recreates them.

---

## How AutoFuzz works

1. `make build` runs `python3 -m autofuzz.main` in `Tests/unit_tests`.
2. **scanner.py** parses `test_common.c` with libclang. It takes every
   non-static function that has parameters, and collects edge values for
   each parameter: values from `config.py` for the type, plus numbers and
   strings it finds in comparisons, `switch` cases and literals.
3. **generator.py** sorts the values and keeps at most `EDGE_CAP` (12) per
   parameter, spread from smallest to largest. It writes:
   - `deterministic_edge_<function>.c`: one CMocka test per value combination
   - `random_fuzz_<function>.c`: a libFuzzer harness
4. The Makefile compiles them with `-fsanitize=address,undefined`
   (and `integer` for fuzzing) and runs them.

The generated files are the same on every run.

### Important: what is tested

AutoFuzz tests `Tests/unit_tests/test_common.c`. This is a **PC copy** of
the firmware logic, not the firmware file `Core/Src/protocol.c` itself
(the Makefile variable `PROD_SRCS` is empty). The copy behaves like the
firmware, but the code is not identical. Bug 2 is also found in the real
firmware by `Tests/fuzz_manual`.

`Tests/unit_tests` also has its own copies of `protocol_defs.h` and
`servo_defs.h`. They are slightly different from `Core/Inc`
(for example `SERVO_MIN_PULSE`/`SERVO_MAX_PULSE`).

Planned next step: run AutoFuzz directly on `Core/Src`.

---

## Use AutoFuzz on your own code

1. Copy `Tests/unit_tests/autofuzz/`, `Makefile` and a `test_common.c/.h`
   that contains (or includes) the functions you want to test.
2. Edit `autofuzz/config.py`: add your commands and, most importantly, your
   **buffer sizes** (size − 1, size, size + 1). Bug 1 was found because
   strings longer than the 1024-byte buffer were in the seed list.
3. Run `make build` and `make test`.

`STUB_SRC` in the Makefile selects the C file that AutoFuzz scans.

---

## Building the firmware

The firmware is built with **STM32CubeIDE** (tested with 1.17), not with the
Makefile in this repository. The CubeIDE project files (`.project`,
`.cproject`) are not in git. In CubeIDE use *File → New → STM32 Project from
an Existing STM32CubeMX Configuration File (.ioc)* and choose
`ServoProject.ioc`.

---

## CI

`.github/workflows/unit-and-fuzz.yml` runs build, unit, edge and fuzz on
every push (with `continue-on-error`, because of the expected findings).

## License

See [LICENSE](LICENSE).
