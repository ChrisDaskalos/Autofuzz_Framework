# `autofuzz.yaml`: the config file

Everything that is specific to your project is in one file, `autofuzz.yaml`.
You never edit the Python code.

```bash
autofuzz init                 # writes a starter autofuzz.yaml here (never overwrites)
autofuzz run                  # reads ./autofuzz.yaml
autofuzz run --config path/to/autofuzz.yaml
```

Your file is merged on top of the defaults in
[`autofuzz/defaults.yaml`](../autofuzz/defaults.yaml). A key you leave out
keeps its default. **Paths are relative to the folder of the YAML file.**

An unknown key (for example a typo like `limts:`), a wrong type or a
missing file stops AutoFuzz with a message that names the key:

```
autofuzz: error: autofuzz.yaml: unknown key 'limts'. Did you mean 'limits'? Allowed keys here: ...
```

## All keys

To start, you must fill in 3 keys: `sources`, `include_dirs` and `harness.includes`.
`autofuzz init` marks them **REQUIRED** in the file it writes. All other keys are optional.

| Key | Type | Default | What it does |
|---|---|---|---|
| `sources` | list of paths | (none, required) | The `.c` files to test. AutoFuzz writes tests for every non-static function defined in them, and compiles and links them into every test program. |
| `fake_include_dirs` | list of paths | `[]` | Folders with fake headers, for example a fake HAL. They come **before** `include_dirs` on the include path, so a fake `stm32f1xx_hal.h` replaces the real one. `builtin:stm32f1_hal` is the fake STM32F1 HAL in [`autofuzz/fakes/stm32f1_hal/`](../autofuzz/fakes/stm32f1_hal/): HAL types and declarations only, no register addresses. A finding whose top stack frame is in a fake header is marked **needs review**. |
| `include_dirs` | list of paths | `[]` (fill in to start) | Folders with the headers your sources include. Passed as `-I`, in this order. |
| `defines` | list | `[]` | Preprocessor defines, passed as `-D`. `UNIT_TEST` or `BUF=64`. |
| `cflags` | list | `[-std=c11]` | More compiler flags. |
| `compiler` | text | `clang` | The C compiler. It must be clang, because libFuzzer is part of clang. `clang-18`, for example. |
| `functions.include` | list of patterns | `[]` (= all) | Test only the functions that match. Shell patterns: `Parser_*`. |
| `functions.exclude` | list of patterns | `[]` | Never test these functions. |
| `limits.edge_cap` | number | `12` | At most this many edge values per parameter. |
| `limits.buffer_size` | number | `4096` | The size of the text buffer a fuzzer gives to a `char *` parameter. |
| `limits.int_ranges` | map | `{}` | The valid range of an integer parameter: `Function.param: [min, max]`. AutoFuzz then tests `min-1, min, min+1, middle, max-1, max, max+1` for that parameter (plus `INT_MIN` and `INT_MAX`, which every integer gets), instead of the default values for its type. Example: `Servo_SetAngle.angle: [0, 180]`. |
| `limits.string_seeds` | list | see below | Text inputs for `char *` parameters. **Added** to the default list. |
| `limits.default_string_seeds` | true/false | `true` | `false` = use only your own `string_seeds`. |
| `harness.includes` | list | `[]` (fill in to start) | Headers that every generated test includes. Together they must declare the functions under test. |
| `harness.setup` | list | `[]` | How to prepare a struct parameter before the call (see below). |
| `fuzz.seconds` | number | `10` | Seconds per fuzzer for `autofuzz run`. `--fuzz-seconds N` overrides it. |
| `output_dir` | path | `autofuzz-out` | Where AutoFuzz writes everything. Add it to `.gitignore`. |
| `baseline` | list | `[]` | Known findings you do not fix yet (see below). `autofuzz run` exits 1 only for a firmware bug that is not in this list. |

### `limits.string_seeds`

You write plain YAML text. AutoFuzz turns each entry into a C string
literal (a tab becomes `"\t"`, the byte 0xFF becomes `"\xff"`).
For long strings, use `repeat`:

```yaml
limits:
  string_seeds:
    - "HELP"
    - "(90,5,95)"
    - "\t"                                         # a tab
    - {repeat: A, times: 1050}                     # 1050 x "A"
    - {repeat: A, times: 1050, prefix: "(", suffix: ")"}
```

The defaults are empty and whitespace strings, CR/LF, zero and 0xFF bytes,
numbers as text, and `A` strings of 63 to 100 characters.

AutoFuzz also adds every string and character literal it finds in the
function body (for example `"1234"` in `strcmp(cmd, "1234")`).

### `harness.setup`

Some functions take a pointer to a struct that must be prepared first,
for example a parser or a protocol state. For each parameter of type
`<type> *`, AutoFuzz declares `<type> <var>;`, runs the `lines`, and
passes `&<var>`:

```yaml
harness:
  includes: [test_common.h]
  setup:
    - type: ProtocolContext
      var: ctx
      lines:
        - reset_ctx(&ctx);
        - ctx.authenticated = 1;
        - ctx.state = STATE_WAIT_SERVO;
```

The generated code is then:

```c
ProtocolContext ctx;
reset_ctx(&ctx);
ctx.authenticated = 1;
ctx.state = STATE_WAIT_SERVO;
Protocol_ProcessCommand(&ctx, a1);
```

If one of the lines calls the function under test itself (here:
`reset_ctx`), the lines are left out for that function. Only the
variable is declared.

### Pointer parameters without `harness.setup`

A pointer parameter (other than `char *`) with no `harness.setup` entry gets
the address of **one zero-filled object** of its type:

```c
/* AUTOFUZZ-ZERO-ARGS: argument 3 (unsigned long *). Add a harness.setup entry for this type to test with real data. */
...
unsigned long afz_zero_a2 = {0};
cli_parse_uint(a0, a1, &afz_zero_a2);
```

If the function reads or writes past that one object (it expected an array),
or hits a NULL pointer inside it (a zero-filled struct has NULL pointer
fields), the finding is marked **needs review (zero-filled argument)**.

It gets **NULL** only when the test cannot create the type: `void *`, a
function pointer, a pointer to an array, or a struct that the headers in
`harness.includes` only declare (`struct sensor;`, defined in a `.c` file).
AutoFuzz checks this with those headers alone, as the generated test sees
them. Then the comment is `/* AUTOFUZZ-NULL-ARGS: argument 1 (const struct sensor *) */`,
and a crash on that NULL is marked **needs review (NULL argument)**.

Neither is counted as a firmware bug. To test the function with real data,
add a setup entry for the pointed-to type. Example from the root `autofuzz.yaml`:

```yaml
    - type: uint8_t          # Servo_Ramp(uint8_t *currentAngle, ...)
      var: current_angle
      lines:
        - current_angle = SERVO_DEFAULT_ANGLE;
```

A `char *` parameter gets a writable copy of each text input (the function
may change it, as `strtok` does). A `const char *` gets the text as it is.

### `baseline`

Findings you know about and do not fix yet: known bugs, or test-caused
findings you have checked. With a baseline, `autofuzz run` can run in CI:
it exits **1 only for a firmware bug that is not in the list**, and the
report marks each firmware bug as `(known)` or `(NEW)`. A required line that
is no longer found is listed at the top of `report.md` (a fixed bug: delete
the line).

One line per finding, in **single quotes** (so YAML keeps the backslashes):

```yaml
baseline:
  - 'edge deterministic_edge_cli_run ASAN global-buffer-overflow ringbuf\.c:34 in ringbuf_push'
  - 'maybe fuzz random_fuzz_cli_execute ASAN global-buffer-overflow ringbuf\.c:34 in ringbuf_push'
  - 'skipped cpu_nop SKIPPED cpu_nop \(src/selftest\.c:\d+\): inline assembly .*'
```

- `edge` / `fuzz` + the test program, or `skipped` + the function name.
- Then a Python regular expression that must match the **whole** finding.
  Findings look like this (also in `report.json`, field `found_by`, and in
  the logs):
  - `UBSAN <kind> <file>:<line>`
  - `ASAN <kind> <file>:<line> in <function>`
  - `ASSERT <file>:<line> in <function>`
  - `LIBFUZZER <reason>` (a crash without a sanitizer report)
  - `REVIEW (<reason>) <one of the above>` (needs review)
  - `SKIPPED <function> (<file>:<line>): <reason>`
- `maybe` at the start: allowed, but not required. Use it for a bug that a
  short fuzzing run finds only sometimes.

The configs in this repository use it: their baselines are the known
findings that `make test` checks.

## The report

After the tests, `autofuzz run` writes `report.md` and `report.json` into
`output_dir` and prints a short summary:

```
>>> Report: 1 firmware bug(s), 0 need review, 0 skipped
    F1   FIRMWARE BUG (known) ringbuf.c:34 in ringbuf_push: Buffer overflow in a global variable: the code reads or writes past its end.
         repeat: autofuzz repro F1
    Full report: .../examples/ringbuf_cli/autofuzz-out/report.md
```

Each finding has an id (`F1`, `F2`, ...), a status (`FIRMWARE BUG`,
`NEEDS REVIEW`, `SKIPPED`), one plain sentence, the sanitizer message, the
file, line, function and line of code, the input (the arguments of the edge
test, or the crash file as text and hex), and the command to repeat it.
The same bug found by the edge test and the fuzzer is shown once.

```
autofuzz repro F1        # run the program again with the same input
autofuzz report          # write the report again from the last logs
```

## Firmware: fake headers, stubs, skipped code, needs review

- **Fake headers** (`fake_include_dirs`) replace headers that only work on the
  board, for example the HAL.
- **Stubs**: AutoFuzz writes `stubs/stubs.c` with a definition for every
  function and global that your sources use but do not define, such as
  `HAL_UART_Transmit` and `huart2`. A stub function counts its calls
  (`autofuzz_calls_<name>`) and returns 0 (`HAL_OK`, NULL, a zeroed struct).
  If a stub returns a pointer, AutoFuzz prints a warning: it is always NULL,
  so a finding after a call to it needs review.
- **Skipped functions**: functions that cannot run on a PC get no test. They are
  listed as `SKIPPED: <function> (<file>:<line>): <reason>`. A function is skipped
  if it has inline assembly, casts an integer constant to a pointer (register
  access, for example `*(uint32_t *)0x40010810 = 1`), or never returns (an
  endless loop with no `break`, `return` or `goto`, as in `main`). To leave out
  other functions, use `functions.exclude`.
- **Needs review**: a finding whose top stack frame is in a generated harness,
  a stub or a fake header, a NULL crash on a NULL argument, or a crash on a
  zero-filled argument (see above), gets the line
  `AUTOFUZZ: NEEDS REVIEW (<reason>): ...` in the log. It may be caused by the
  test, so it is not counted as a firmware bug.

[`Tests/autofuzz_selftest/`](../Tests/autofuzz_selftest/) has one example of each.

## What is in `output_dir`

```
autofuzz-out/
  gen/        deterministic_edge_<fn>.c and random_fuzz_<fn>.c
              (and skipped.txt: the skipped functions with the reason)
  stubs/      stubs.c: stubs for what the sources use but do not define
  build/      object files of your sources
  bin/        the test programs (run one by hand to repeat it)
  logs/       edge.log and fuzz.log
  report.md   the report: every finding in plain words (report.json: the same as data)
  crashes/    inputs that made a fuzzer crash
  corpus/     one folder per fuzzer; inputs kept between runs
```

`autofuzz clean` removes these folders and the report. `autofuzz run --fresh`
removes only `logs/`, `crashes/`, `corpus/` and the report first.

## Examples

- [`autofuzz.yaml`](../autofuzz.yaml) in the repository root: the **real servo
  firmware** (`Core/Src`), with the fake HAL and `harness.setup` entries.
  `python3 -m autofuzz run`
- [`Tests/legacy_thesis/autofuzz.yaml`](../Tests/legacy_thesis/autofuzz.yaml):
  the legacy thesis example (the PC copy `test_common.c`).
  `python3 -m autofuzz run --config Tests/legacy_thesis/autofuzz.yaml`
- [`Tests/autofuzz_selftest/autofuzz.yaml`](../Tests/autofuzz_selftest/autofuzz.yaml):
  a tiny project with skipped functions, stubs and test-caused crashes.
- [`examples/ringbuf_cli/autofuzz.yaml`](../examples/ringbuf_cli/autofuzz.yaml):
  a second, unrelated C project with one bug on purpose
  (walk-through: [GETTING_STARTED.md](GETTING_STARTED.md)).

The root `make test` runs all four.

## Same input, same output

The same YAML and the same sources always give the same generated files,
byte for byte: functions and values are sorted, and there are no
timestamps. `make check-determinism` checks this (it is part of `make test`).
