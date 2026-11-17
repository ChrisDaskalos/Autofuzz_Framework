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
**NULL**. Each generated file then says so in a comment
(`/* AUTOFUZZ-NULL-ARGS: argument 1 (const int *) */`). If the function crashes
on that NULL, the finding is marked **needs review (NULL argument)**, not
counted as a firmware bug. To test the function for real, add a setup entry
for the pointed-to type. Example from the root `autofuzz.yaml`:

```yaml
    - type: uint8_t          # Servo_Ramp(uint8_t *currentAngle, ...)
      var: current_angle
      lines:
        - current_angle = SERVO_DEFAULT_ANGLE;
```

A `char *` parameter gets a writable copy of each text input (the function
may change it, as `strtok` does). A `const char *` gets the text as it is.

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
  a stub or a fake header, or a NULL crash on a NULL argument, gets the line
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
  crashes/    inputs that made a fuzzer crash
  corpus/     one folder per fuzzer; inputs kept between runs
```

`autofuzz clean` removes these folders. `autofuzz run --fresh` removes
only `logs/`, `crashes/` and `corpus/` first.

## Examples

- [`autofuzz.yaml`](../autofuzz.yaml) in the repository root: the **real servo
  firmware** (`Core/Src`), with the fake HAL and `harness.setup` entries.
  `python3 -m autofuzz run`
- [`Tests/legacy_thesis/autofuzz.yaml`](../Tests/legacy_thesis/autofuzz.yaml):
  the legacy thesis example (the PC copy `test_common.c`).
  `python3 -m autofuzz run --config Tests/legacy_thesis/autofuzz.yaml`
- [`Tests/autofuzz_selftest/autofuzz.yaml`](../Tests/autofuzz_selftest/autofuzz.yaml):
  a tiny project with skipped functions, stubs and test-caused crashes.

The root `make test` runs all three.

## Same input, same output

The same YAML and the same sources always give the same generated files,
byte for byte: functions and values are sorted, and there are no
timestamps. `make check-determinism` checks this (it is part of `make test`).
