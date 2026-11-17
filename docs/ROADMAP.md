# AutoFuzz 1.0 roadmap

**Goal:** AutoFuzz 1.0 is a test tool that a developer runs on a PC, on their own C
firmware project, to find coding errors before the code goes on the board.

**Not goals:** working on every firmware, testing code that talks directly to hardware
registers, a graphical interface.

## Version 1.0 checklist

- [x] 1. A fresh clone works with 3 commands, and GitHub Actions is green. (`phase1-runnable`)
- [x] 2. A new person understands the project in 10 minutes from the docs. (`m2-docs`)
- [x] 3. The user runs one command and edits one config file (`autofuzz.yaml`). Nobody edits Python code. (`m3-config`)
- [x] 4. It tests the real source files of the servo project, not the copy `test_common.c`. (`m4-real-sources`)
- [x] 5. It also works on a second, small C project, to show that it is not tied to this firmware. (M5)
- [ ] 6. The report says in plain words what failed: file, line, input, and the command to repeat it. (M6)

## Design rules

- The real source files are compiled on the PC with fake headers and generated stubs.
  Code that cannot be tested on a PC is skipped, and the tool says so clearly.
- `autofuzz.yaml` holds everything that is specific to a project: sources, include dirs,
  defines, functions to include or exclude, valid input limits, and run time. No paths are hard-coded.
- The same input gives the same generated files.
- A finding caused by the test code or by a stub is marked **needs review**. It is never
  counted as a firmware bug.
- `test_common.c` stays as a "legacy thesis example".
- It must run on Ubuntu 20.04 with Python 3.8 (the developer VM). Docker is checked by GitHub Actions.
- Never touch the tag `thesis-v1` or the old branches (`master`, `test`, `backup-nov2026`).

## How each milestone is done

When asked "Do the next milestone in docs/ROADMAP.md":

1. Create the milestone branch from the previous milestone branch.
2. Show the plan and wait for approval.
3. Make one commit per step. Run `make test` after each step; it must end with `All results as expected`.
4. Do not push.
5. Tick the checklist above.
6. End with a summary in very simple English: what changed, why, and the commands to try.

## Facts checked before the roadmap was written

Thesis findings: where they really are.

| Finding | In `test_common.c` (copy) | In the real `Core/Src` | Evidence |
|---|---|---|---|
| Bug 1: stack buffer overflow (command of 1024+ characters) | yes | **no** | Copy: `char buf[DMA_BUFFER_SIZE]` (`Tests/unit_tests/test_common.c:117`) has no room for `\0`. Real: `char lineBuffer[DMA_BUFFER_SIZE + 1] = {0}` (`Core/Src/main.c:83`), so the string always ends with `\0`. |
| Bug 2: signed overflow in `angle + step` | yes (`test_common.c:162`) | **yes** (`Core/Src/protocol.c:159`) | Found by the edge test, the generated fuzzer, and `Tests/fuzz_manual`. |
| The 4 failing unit tests (spaces around `B`, a 4th field, step 0, negative step) | yes | **yes** | The same logic is in `Core/Src/protocol.c`. Step 0 and a negative step then reach `assert` in `Servo_Ramp` (`Core/Src/servo.c`). |

Python 3.8: the code uses `:=` (allowed in 3.8). It does not use `list[int]`-style type hints
(those need 3.9). `libclang==18.1.1` and `PyYAML` both work with 3.8. clang-10 on the
VM already runs `make test` with the fuzzers.

---

## M2 – Docs and honest findings

**Branch:** `m2-docs` (from `phase1-runnable`)

**Goal:** in 10 minutes, a new person knows what the project is, what it found, and what is legacy.

**Steps**
1. `git mv Tests/unit_tests Tests/legacy_thesis`. Update the paths in both Makefiles,
   `Tests/check_results.py`, `Tests/expected_findings.txt`, CI, `Dockerfile`, `.gitignore`
   and the docs. The findings must not change.
2. `docs/FINDINGS.md`: the table above, with more detail. Bug 1 is in the legacy copy only. Bug 2 is real.
   The 4 unit-test behaviours are real.
3. `docs/ARCHITECTURE.md`: one diagram of the flow: firmware → generator → harnesses →
   sanitizers → `check_results.py`.
4. `docs/HOW_IT_WORKS.md`, in very simple English. It has one worked example that follows one
   function (`ComputeChecksumFromNumbers`) through these stages:
   source code → scanner → edge values → generated `deterministic_edge_*.c` and `random_fuzz_*.c`
   → compiled with sanitizers → run → the real UBSan output (copied from `Tests/results/`).
   It also has a glossary of these words: harness, corpus, dictionary, sanitizer, libFuzzer, CMocka, stub, edge test.
5. Make `README.md` shorter. It keeps: what the project is, a quick start with 3 commands, the expected output,
   and links to the `docs/` files.
6. Update `CLAUDE.md` with the new paths.

**Files touched:** `Tests/legacy_thesis/**`, `Makefile`, `Tests/check_results.py`,
`Tests/expected_findings.txt`, `.github/workflows/unit-and-fuzz.yml`, `Dockerfile`, `.gitignore`,
`README.md`, `docs/FINDINGS.md`, `docs/ARCHITECTURE.md`, `docs/HOW_IT_WORKS.md`, `CLAUDE.md`.

**How we verify**
- `make clean && make build && make test` → `All results as expected`.
- CI is green after the user pushes.
- A new reader can answer from README + docs: "Which findings are real, and which are only in the legacy copy?"

## M3 – One command, one config file

**Branch:** `m3-config` (from `m2-docs`)

**Goal:** `autofuzz run` (the same as `python3 -m autofuzz run`) reads `./autofuzz.yaml`.
Every project-specific setting comes from the YAML.

**Steps**
1. Move the package to the top level: `Tests/legacy_thesis/autofuzz/` → `autofuzz/`. Add
   `pyproject.toml` (Python ≥ 3.8, dependencies `libclang` and `PyYAML`). Then `pip install .`
   works and also installs the short command `autofuzz`
   (`[project.scripts] autofuzz = "autofuzz.__main__:main"`).
2. `autofuzz/config.py` loads and checks `autofuzz.yaml`. Keys: `sources`, `include_dirs`, `defines`,
   `functions.include` / `functions.exclude`, `limits` (integer ranges, buffer sizes, string seeds),
   `fuzz.seconds`, `output_dir`. An unknown key or a missing file gives a clear error. The default
   edge values move out of the Python code and into the YAML defaults.
3. `autofuzz/runner.py` and `autofuzz/__main__.py` with these subcommands:
   - `autofuzz init`: writes a starter `autofuzz.yaml` in the current folder. Above each key there is a
     comment that says what the key does, with an example. It never overwrites an existing file.
   - `autofuzz run`: generate + build + run.
   - `autofuzz generate`, `autofuzz clean`.

   It compiles with clang through `subprocess`, so the user's project needs no Makefile. The output
   goes to `autofuzz-out/`, which git ignores.
4. Same input, same output: functions and values are sorted, and there are no timestamps. A check runs `generate`
   twice and compares the two outputs with `diff -r`.
5. `Tests/legacy_thesis/autofuzz.yaml` points to `test_common.c`, so it has the same targets as today. The root `make test`
   calls `autofuzz run --config Tests/legacy_thesis/autofuzz.yaml`. The findings stay the same.
6. Python 3.8 check: a new CI job runs `make deps`, `make build` and `make test` in a Docker image based on `ubuntu:20.04`
   (Python 3.8 + clang-10). clang-10 on the VM already ran `make test` with the fuzzers, so no upgrade is
   expected. `docs/INSTALL.md` lists the exact `apt` and `pip` commands for the VM.

**Files touched:** `autofuzz/**`, `pyproject.toml`, `requirements.txt`,
`Tests/legacy_thesis/Makefile`, `Tests/legacy_thesis/autofuzz.yaml`, `Makefile`,
`Tests/check_results.py`, `.github/workflows/unit-and-fuzz.yml`, `Dockerfile`, `.gitignore`,
`docs/CONFIG.md`, `docs/INSTALL.md`.

**How we verify**
- `make test` → the same result as before.
- In an empty folder, `autofuzz init` writes an `autofuzz.yaml` with a comment for each key.
- `grep -rn "test_common\|Core/" autofuzz/` finds no hard-coded paths.
- The `generate`-twice diff is empty.
- The Ubuntu 20.04 CI job is green. The user runs it on the VM.

## M4 – Test the real firmware sources

**Branch:** `m4-real-sources` (from `m3-config`)

**Goal:** the root `autofuzz.yaml` targets `Core/Src/protocol.c` and `Core/Src/servo.c`.
Code that cannot run on a PC is skipped, and the tool gives the reason.

**Steps**
1. Fake headers in `autofuzz/fakes/stm32f1_hal/`. They contain only the HAL types and declarations the code uses
   (UART and timer handles, `HAL_StatusTypeDef`, `HAL_Delay`, …) and no CMSIS register addresses.
   They go first on the include path, set with `fake_include_dirs` in the YAML.
2. `autofuzz/stubgen.py` uses libclang to find the functions and globals that the selected sources use but do not
   define (`HAL_UART_Transmit`, `huart2`, …). It generates stub bodies that return 0 or `HAL_OK` and count
   the calls, and writes them to `autofuzz-out/stubs/`.
3. Skip detection. These functions are skipped and listed as `SKIPPED: <reason>` in the output and the report:
   functions that cast an integer constant to a pointer (register access), functions with inline asm,
   and functions that never return (`while(1)` with no `break`, for example `main`).
4. The real sources are compiled **without** `-DUNIT_TEST`. The `#ifdef UNIT_TEST` blocks in `Core/Src`
   stay, for `Tests/fuzz_manual` and the IDE build. The firmware does not change.
5. "Needs review": if the top stack frame of a finding is in a generated harness, a stub or a fake
   header, the finding is marked "needs review". It is not counted as a firmware bug.
6. Add the new real findings to `Tests/expected_findings.txt`. Expected: bug 2 at `protocol.c:159`, and the
   `assert` in `Servo_Ramp` for step 0. Bug 1 must **not** be found; this confirms `docs/FINDINGS.md`.

**Files touched:** `autofuzz.yaml` (root), `autofuzz/stubgen.py`, `autofuzz/scanner.py`,
`autofuzz/generator.py`, `autofuzz/runner.py`, `autofuzz/fakes/**`, `Tests/expected_findings.txt`,
`Tests/check_results.py`, `docs/FINDINGS.md`, `docs/CONFIG.md`.

**How we verify**
- `make test` → `All results as expected`.
- `autofuzz run` in the repo root lists the targets, the skipped functions with their reasons, and the real findings.
- `git diff thesis-v1 -- Core/` is empty. The user checks that the firmware still builds in STM32CubeIDE.

## M5 – A second project

**Branch:** `m5-second-project` (from `m4-real-sources`)

**Goal:** show that AutoFuzz is not tied to the servo firmware.

**Steps**
1. `examples/ringbuf_cli/`: a new, small project in plain C (about 200 lines: a ring buffer and a text
   command parser). It has its own `src/` and `include/` folders, a different layout from `Core/`. It has
   one documented bug, added on purpose: an off-by-one in a ring-buffer index.
2. It has its own `examples/ringbuf_cli/autofuzz.yaml` and needs no fake headers. Ideally the Python code
   does not change. If it must change, the change is a general fix in its own commit.
3. `make test` also runs the example and checks its expected findings
   (`examples/ringbuf_cli/expected_findings.txt`).
4. `docs/GETTING_STARTED.md`: "Use AutoFuzz on your own project", with this example as the walk-through.

**Files touched:** `examples/ringbuf_cli/**`, `Makefile`, `Tests/check_results.py`, `autofuzz/stubgen.py`
(general fix: a `static` global without `= ...` is defined, not stubbed),
`.github/workflows/unit-and-fuzz.yml`, `docs/GETTING_STARTED.md`.

**How we verify**
- `cd examples/ringbuf_cli && autofuzz run` finds the off-by-one at the correct file and line.
- `make test` → `All results as expected`.

## M6 – A report in plain words

**Branch:** `m6-report` (from `m5-second-project`)

**Goal:** the report explains each finding in plain words and gives what you need to repeat it.

**Steps**
1. `autofuzz/report.py` parses the sanitizer, CMocka and libFuzzer output (it reuses the parsing in
   `Tests/check_results.py`) and removes duplicates by (kind, file, line).
2. For each finding the report shows:
   - the status: `FIRMWARE BUG`, `NEEDS REVIEW` or `SKIPPED`;
   - one plain sentence, for example "Signed integer overflow: the sum of angle and step is too big for int";
   - the file, line and function;
   - the input, as hex and as printable text, with the path to the saved input file;
   - the **command to repeat it**: `autofuzz repro <id>`, and also the raw command for the test binary.
3. It writes `autofuzz-out/report.md` and prints a short summary in the terminal. The exit code is 1 if it finds a
   firmware bug that is not in the baseline.
4. The baseline moves into the tool: a `baseline:` key in the YAML replaces `Tests/expected_findings.txt`.
   `check_results.py` becomes a thin wrapper, or is removed.
5. A final pass over all the docs. Tick the whole checklist, and propose the tag `v1.0` (the user creates it).

**Files touched:** `autofuzz/report.py`, `autofuzz/runner.py`, `autofuzz/__main__.py`, all
`autofuzz.yaml` files, `Tests/check_results.py`, `Makefile`, `.github/workflows/unit-and-fuzz.yml`, `docs/*.md`.

**How we verify**
- Change a known input on purpose. The report shows the file, line and input, and a repeat command that
  reproduces the crash when you copy it as it is.
- `make test` → `All results as expected`. The Ubuntu 20.04 CI job is green.

---

## Final folder structure (after M6)

```
autofuzz/                 the tool (Python package; `pip install .` gives the `autofuzz` command)
  __main__.py  config.py  scanner.py  stubgen.py  generator.py  runner.py  report.py  clang_helper.py
  rt/autofuzz_rt.h        runtime helpers for the generated harnesses
  fakes/stm32f1_hal/      fake HAL headers (types and declarations only)
autofuzz.yaml             config for the servo firmware (Core/Src)
pyproject.toml  requirements.txt  Makefile  Dockerfile
Core/  Drivers/  ServoProject.ioc     the STM32 firmware (not changed)
examples/ringbuf_cli/     the second project: src/ include/ autofuzz.yaml expected_findings.txt
Tests/
  legacy_thesis/          test_common.c, hand-written CMocka tests, autofuzz.yaml (the thesis example)
  fuzz_manual/            hand-written fuzzers for the real firmware (not changed)
  check_results.py        a thin wrapper, or removed in M6
docs/
  ROADMAP.md  FINDINGS.md  ARCHITECTURE.md  HOW_IT_WORKS.md  INSTALL.md  CONFIG.md  GETTING_STARTED.md
autofuzz-out/             generated output, ignored by git
```
