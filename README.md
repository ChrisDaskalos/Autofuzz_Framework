# AutoFuzz: automatic edge tests and fuzzing for STM32 servo firmware

AutoFuzz is the tool from my MSc thesis. It reads C code with **libclang**,
finds the functions, and writes two kinds of tests for each one:

- **edge tests**: CMocka tests that call the function with boundary values
  (`INT_MIN`, `INT_MAX`, an empty string, a very long string, …);
- **fuzz harnesses**: libFuzzer programs that call the function with random inputs.

Everything is compiled with AddressSanitizer and UndefinedBehaviorSanitizer,
so memory errors and integer overflows are reported with a file and line.
At the end, AutoFuzz writes a **report** that explains each finding in plain
words, with the input and the command to repeat it.

The example target is firmware for an STM32F103 that moves a servo motor,
using commands it receives over UART.

AutoFuzz tests the real firmware files `Core/Src/protocol.c` and `servo.c`
(root [`autofuzz.yaml`](autofuzz.yaml)), compiled as on the board, with a fake
HAL and generated stubs. The thesis version tested a PC copy of the logic; that
copy is kept as the legacy example in `Tests/legacy_thesis/`.

## Quick start

With **Docker**:

```bash
docker build -t autofuzz .
docker run --rm autofuzz          # runs `make test` (about 5 minutes)
```

Or on **Ubuntu 24.04** (first install the tools:
`sudo apt install clang-18 libclang-rt-18-dev build-essential libcmocka-dev python3-venv`,
then `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`):

```bash
make deps      # checks that everything is installed
make build     # generates the tests and compiles them
make test      # runs all tests and compares the findings with the expected list
```

If `clang` is not found: `sudo ln -s /usr/bin/clang-18 /usr/local/bin/clang`.
Ubuntu 20.04 / Python 3.8 works too: see [docs/INSTALL.md](docs/INSTALL.md).

## Use it on your own C code

```bash
pip install .          # gives the `autofuzz` command
cd my-project
autofuzz init          # writes autofuzz.yaml; fill in the 3 REQUIRED keys
autofuzz run           # checks the tools, generates, compiles, runs, writes the report
autofuzz repro F1      # repeats finding F1 of the report
```

The report (`autofuzz-out/report.md`) looks like this, for the example
project [`examples/ringbuf_cli`](examples/ringbuf_cli/) and its bug:

```
>>> Report: 1 firmware bug(s), 0 need review, 0 skipped
    F1   FIRMWARE BUG (known) ringbuf.c:34 in ringbuf_push: Buffer overflow in a global variable: the code reads or writes past its end.
         repeat: autofuzz repro F1
```

Step by step, with a small example project and its bug:
[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).
All settings are in `autofuzz.yaml`: [docs/CONFIG.md](docs/CONFIG.md).

## Expected output

The tests are **meant to find bugs** (the thesis results). `make test` passes
when the findings are exactly the known ones: the `baseline:` in each
`autofuzz.yaml`, and [`Tests/expected_findings.txt`](Tests/expected_findings.txt)
for the hand-written tests:

```
============================ RESULTS ============================
  unit            5 findings  (expected: 5 required; new: 0)
  legacy-edge     2 findings  (expected: 2 required; new: 0)
  legacy-fuzz     2 findings  (expected: 1 required + 2 maybe; new: 0)
  legacy-skipped  0 findings  (expected: 0 required; new: 0)
  self-edge       2 findings  (expected: 2 required; new: 0)  [2 need review, not firmware bugs]
  self-fuzz       3 findings  (expected: 3 required; new: 0)  [3 need review, not firmware bugs]
  self-skipped    3 findings  (expected: 3 required; new: 0)
  real-edge       3 findings  (expected: 3 required; new: 0)
  real-fuzz       3 findings  (expected: 2 required + 1 maybe; new: 0)
  real-skipped    0 findings  (expected: 0 required; new: 0)
  ex-edge         1 findings  (expected: 1 required; new: 0)
  ex-fuzz         2 findings  (expected: 2 required; new: 0)
  ex-skipped      0 findings  (expected: 0 required; new: 0)
  manual          2 findings  (expected: 2 required; new: 0)
  Expected: `baseline:` in each autofuzz.yaml, and Tests/expected_findings.txt (unit, manual)
  Logs: Tests/results/
=================================================================
All results as expected
```

Exit code 0 means "as expected". Exit code 1 and a last line starting with
`UNEXPECTED:` means something is different (a new bug, or a known bug that is gone).

`legacy-*` is the thesis example (a PC copy of the logic), `real-*` the real
firmware, `ex-*` the second project `examples/ringbuf_cli` (its off-by-one
bug), `self-*` the AutoFuzz self-test (its findings are caused on purpose),
`unit` and `manual` the hand-written tests.

**What was found:** one real bug in the firmware (a signed integer overflow
in the checksum, `Core/Src/protocol.c:159`), an `assert` in `Servo_Ramp` that a
step of 0 reaches, four protocol behaviours that the unit tests do not accept,
and one bug that exists only in the legacy copy. `main.c` (the UART/DMA receive
path) is not tested by AutoFuzz.
Details: [docs/FINDINGS.md](docs/FINDINGS.md). It also explains a problem
fixed in 1.0 that the thesis version had: its generated fuzzers ran without
coverage feedback.

## Documents

| Document | Read it to learn |
|---|---|
| [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) | how to use AutoFuzz on your own project, with `examples/ringbuf_cli` |
| [docs/FINDINGS.md](docs/FINDINGS.md) | which findings are real firmware bugs, and which are only in the legacy copy |
| [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) | one function, step by step, from the C code to the error message; glossary |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | the flow diagram, all `make` commands, the folder map, CI, building the firmware |
| [docs/INSTALL.md](docs/INSTALL.md) | the exact install commands (Ubuntu 20.04 and 24.04, Docker) |
| [docs/CONFIG.md](docs/CONFIG.md) | every key of `autofuzz.yaml`, with examples |
| [docs/ROADMAP.md](docs/ROADMAP.md) | the plan for AutoFuzz 1.0, and ideas for after it |
| [Tests/fuzz_manual/README.md](Tests/fuzz_manual/README.md) | the hand-written fuzzers for the real firmware |

## AI assistance

The AutoFuzz tool was refactored for version 1.0 with the help of
[Claude Code](https://claude.com/claude-code) (an AI coding assistant). The
author reviewed the changes. The thesis version is kept unchanged as the tag
`thesis-v1`.

## License

AutoFuzz and the firmware code written for this project: MIT, see
[LICENSE](LICENSE). The STM32 HAL and CMSIS files in `Drivers/` and the
CubeMX-generated files keep their own licenses: see
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
