# Use AutoFuzz on your own project

This page walks through AutoFuzz on a small C project that has nothing to do
with the servo firmware: [`examples/ringbuf_cli/`](../examples/ringbuf_cli/),
a ring buffer and a text command parser (about 200 lines). It has one bug,
added on purpose. At the end AutoFuzz shows you that bug with file and line.

Do the same steps in your own project.

You need: clang, CMocka, Python 3.8+ with `libclang` and `PyYAML`.
See [INSTALL.md](INSTALL.md). `autofuzz check` tells you what is missing.

In the commands below, `autofuzz` means one of:

```bash
autofuzz ...                                    # after `pip install .` in this repository
PYTHONPATH=/path/to/this/repo python3 -m autofuzz ...   # without installing
```

## 1. The project

```
examples/ringbuf_cli/
├── include/
│   ├── ringbuf.h      ringbuf_init, ringbuf_push, ringbuf_pop, ringbuf_peek, ...
│   └── cli.h          cli_run("fill 8;pop;push 42"), cli_execute, cli_parse_uint
└── src/
    ├── ringbuf.c
    └── cli.c
```

AutoFuzz tests C functions directly on your PC. It does not need a `main()`
or a build system of your own: you tell it which `.c` files and which header
folders to use.

## 2. Create `autofuzz.yaml`

In the project folder:

```bash
cd examples/ringbuf_cli
autofuzz init        # writes autofuzz.yaml with every key and a comment for each
```

(The example already has its `autofuzz.yaml`, so `init` stops there; in a new
project it writes one.) Fill in the 3 keys marked REQUIRED:

```yaml
sources:              # the .c files to test (their non-static functions)
  - src/ringbuf.c
  - src/cli.c

include_dirs:         # folders with the .h files (-I)
  - include

harness:
  includes:           # headers that declare the functions under test
    - ringbuf.h
    - cli.h
```

That is already enough to run. All keys: [CONFIG.md](CONFIG.md).

## 3. Tell AutoFuzz about your inputs (optional, but it finds much more)

**Pointer parameters.** `ringbuf_push(ringbuf_t *rb, uint8_t value)` needs a
real ring buffer. Without help AutoFuzz passes one zero-filled `ringbuf_t`:
its `data` is NULL and `cap` is 0, so every push is refused and nothing
interesting is tested. (If a crash comes from such an object, it is marked
*needs review*: it is caused by the test, not by your code. A type the test
cannot create, like `void *`, gets NULL.) Tell it how to prepare a real one:

```yaml
harness:
  setup:
    - type: ringbuf_t           # for every `ringbuf_t *` parameter
      var: rb
      lines:
        - static uint8_t rb_storage[8];
        - ringbuf_init(&rb, rb_storage, sizeof rb_storage);
```

**Text inputs.** `cli_run(const char *script)` takes commands. Random text
rarely becomes a valid command, so give some examples. AutoFuzz also adds the
text literals it finds in your code (`"push"`, `"pop"`, ...):

```yaml
limits:
  default_string_seeds: false   # the input is a script; skip the generic "", "AAAA...", numbers
  string_seeds:
    - "count"
    - "push 1 2 3"
    - "fill 8"
    - "fill 8;count;peek 7;pop;pop;count;clear;fill 3;peek 2;push 255 0 7;count;pop;pop;pop"
    - "clear;fill 8;count;peek 0;peek 7;pop;count;push 42;count;peek 7;pop;pop;pop;pop;pop;pop;pop;pop"
```

An edge test uses at most 12 seeds per parameter, spread from the shortest to
the longest. The longest is always kept.

Your project does not need fake headers or stubs: it uses only the C library.
(Firmware that calls a HAL does. See the root `autofuzz.yaml` and
[CONFIG.md](CONFIG.md) for `fake_include_dirs`. Functions you use but do not
define get generated stubs automatically.)

## 4. Run

```bash
autofuzz run          # check tools, generate tests, compile, run edge tests, then fuzz 10 s each
```

Output (shortened):

```
autofuzz: targets -> cli_execute, cli_output, cli_parse_uint, cli_run, ringbuf_clear, ...
>>> Running edge tests...
=== EDGE: deterministic_edge_cli_execute === ok
=== EDGE: deterministic_edge_cli_parse_uint === ok
=== EDGE: deterministic_edge_cli_run === FOUND SOMETHING
    SUMMARY: AddressSanitizer: global-buffer-overflow .../examples/ringbuf_cli/src/ringbuf.c:34:24 in ringbuf_push
=== EDGE: deterministic_edge_ringbuf_clear === ok
...
>>> Running fuzzers (10 s each)...
=== FUZZ: random_fuzz_cli_run (10s) === ok
...
>>> 1 program(s) found something. Logs: .../autofuzz-out/logs  Crash inputs: .../autofuzz-out/crashes
```

Everything is written to `autofuzz-out/` (add it to `.gitignore`):

| Folder | What is in it |
|---|---|
| `gen/` | the generated tests: `deterministic_edge_<fn>.c`, `random_fuzz_<fn>.c` |
| `stubs/` | `stubs.c` (here: "Nothing to stub") |
| `bin/` | the compiled test programs |
| `logs/` | `edge.log`, `fuzz.log`: the full output |
| `crashes/` | inputs that made a fuzzer crash |

Useful options: `--only edge`, `--only fuzz`, `--fuzz-seconds 60`, `--fresh`
(forget old corpus and crashes).

## 5. Read the finding

`autofuzz-out/logs/edge.log` has the full report:

```
[ RUN      ] test_cli_run_edge_7
==18824==ERROR: AddressSanitizer: global-buffer-overflow on address 0x000000da2168 ...
WRITE of size 1 at 0x000000da2168 thread T0
    #0 0x4c3d14 in ringbuf_push .../examples/ringbuf_cli/src/ringbuf.c:34:24
    #1 0x4c61e4 in cmd_push .../examples/ringbuf_cli/src/cli.c:48:13
    #2 0x4c5a79 in cli_execute .../examples/ringbuf_cli/src/cli.c:88:16
    #3 0x4c68bf in cli_run .../examples/ringbuf_cli/src/cli.c:145:25
    #4 0x4c34d2 in test_cli_run_edge_7 .../autofuzz-out/gen/deterministic_edge_cli_run.c:80:5
...
0x000000da2168 is located 0 bytes to the right of global variable 'g_storage' defined in '.../src/cli.c:12:16' (0xda2160) of size 8
```

Read it from the top:

- **What:** a WRITE of 1 byte, 0 bytes to the right of the 8-byte array
  `g_storage`. So something wrote `g_storage[8]`, one past the end.
- **Where:** frame `#0`, `src/ringbuf.c:34`: `rb->data[rb->head] = value;`.
- **With which input:** `test_cli_run_edge_7` in
  `autofuzz-out/gen/deterministic_edge_cli_run.c` calls
  `cli_run("clear;fill 8;...;pop;count;push 42;...")`: fill the buffer, take
  one byte out, add one.

The cause is two lines further down:
`if (rb->head > rb->cap)` must be `>=`, so `head` reaches 8 instead of going
back to 0 (see [the example's README](../examples/ringbuf_cli/README.md)).

If the top frame is in AutoFuzz's own code (`gen/`, `stubs/`, fake headers)
or the crash is on a NULL or zero-filled argument that AutoFuzz passed, the log also says
`AUTOFUZZ: NEEDS REVIEW (...)`: then check the test, not your code first.

## 6. Repeat it

The edge test is a normal program; run it again as often as you like:

```bash
./autofuzz-out/bin/deterministic_edge_cli_run
```

A fuzzer also takes an input file. For a fuzz finding, give it the file
from `autofuzz-out/crashes/`. You can also write a smaller input yourself:

```bash
printf 'fill 8;pop;push 1' > bug.txt
./autofuzz-out/bin/random_fuzz_cli_run bug.txt
# SUMMARY: AddressSanitizer: global-buffer-overflow .../src/ringbuf.c:34:24 in ringbuf_push
```

After you fix the bug, run `autofuzz run --fresh` again: the line should say
`ok`.

## 7. Common errors and how to fix them

These are real messages, copied from runs on a broken copy of
`examples/ringbuf_cli` (long paths shortened to `.../`). An error in
`autofuzz.yaml` stops AutoFuzz with exit code 2 before anything is compiled.

**`sources` is still empty** (right after `autofuzz init`):

```
autofuzz: error: .../autofuzz.yaml: 'sources' is empty. List the .c files to test, e.g.
  sources:
    - src/parser.c
```

Fix: fill in the 3 REQUIRED keys (step 2).

**A typo in a key name:**

```
autofuzz: error: .../autofuzz.yaml: unknown key 'include_dir'. Did you mean 'include_dirs'? Allowed keys here: cflags, compiler, defines, fake_include_dirs, functions, fuzz, harness, include_dirs, limits, output_dir, sources.
```

Fix: use the suggested name. Unknown keys are always an error, so a typo
cannot be silently ignored.

**A wrong path:**

```
autofuzz: error: .../autofuzz.yaml: source file not found: .../src/clii.c (paths are relative to .../examples/ringbuf_cli)
autofuzz: error: .../autofuzz.yaml: include_dirs / fake_include_dirs folder not found: .../inc
```

Fix: paths are relative to the folder of `autofuzz.yaml`, not to the folder
you run the command in.

**A header is not found** (the folder exists, but it is the wrong one):

```
autofuzz: error: could not compile .../src/ringbuf.c:
.../src/ringbuf.c:7:10: fatal error: 'ringbuf.h' file not found
#include "ringbuf.h"
         ^~~~~~~~~~~
```

Fix: add the folder that contains `ringbuf.h` to `include_dirs`. For a
header that only exists on the target (a HAL, `stm32f1xx.h`), use a fake
header in `fake_include_dirs` (see [CONFIG.md](CONFIG.md)).

**No function to test:**

```
autofuzz: left out by functions.include/exclude -> cli_execute, cli_output, cli_parse_uint, cli_run, ringbuf_clear, ...
autofuzz: no target functions found in 'sources'.
```

Fix: the patterns in `functions.include` match no function (here
`[Parser_*]`). Leave `include` empty to test every non-static function.
`static` functions are never tested directly; they are tested through the
functions that call them.

**A tool is missing** (`autofuzz check`, also run by `autofuzz run`):

```
autofuzz: some tools are missing:
  MISSING  clang-99 (the C compiler set by 'compiler:' in autofuzz.yaml)
           install:  install clang-99, or set 'compiler: clang' in autofuzz.yaml
Install them and run the command again. (docs/INSTALL.md has the full list.)
```

Fix: run the install command it prints. [INSTALL.md](INSTALL.md) has them all.

**Not errors, but read them** (from the AutoFuzz self-test,
`Tests/autofuzz_selftest`):

```
autofuzz: SKIPPED: cpu_nop (src/selftest.c:64): inline assembly (runs only on the target CPU)
autofuzz: SKIPPED: led_on (src/selftest.c:58): casts an integer constant to a pointer (hardware register access)
autofuzz: SKIPPED: run_forever (src/selftest.c:70): never returns (endless loop with no break or return)
```

These functions cannot run on a PC, so they get no tests (list in
`autofuzz-out/gen/skipped.txt`). Exclude them with `functions.exclude` to
silence the message, or move the hardware access into a separate function.

```
autofuzz: WARNING: stub board_name() returns a pointer (always NULL). A finding after a call to board_name needs review.
```

Your code calls a function that AutoFuzz had to stub. The stub returns NULL.
If your code then uses that pointer, the crash is caused by the stub. Fix:
add the real `.c` file that defines it to `sources`, or a fake in
`fake_include_dirs`.

```
AUTOFUZZ: NEEDS REVIEW (zero-filled argument: the test passed a zero-filled object for argument 1 (const int *); add a harness.setup entry for its type): SUMMARY: AddressSanitizer: stack-buffer-overflow .../src/selftest.c:59:23 in sum3
AUTOFUZZ: NEEDS REVIEW (NULL argument: the test passed NULL for argument 1 (const struct sensor *)): SUMMARY: UndefinedBehaviorSanitizer: null-pointer-use .../src/selftest.c:70:15 in
AUTOFUZZ: NEEDS REVIEW (top frame in fake header: board.h): SUMMARY: UndefinedBehaviorSanitizer: integer-divide-by-zero .../fakes/board.h:19:14 in
```

The crash is probably caused by the test, not by your code:

- **zero-filled argument**: AutoFuzz passed ONE zero-filled object, and
  `sum3` reads three `int`s from it (it expects an array).
- **NULL argument**: AutoFuzz cannot create a `struct sensor` (the header
  only declares it), so it passed NULL.
- **top frame in fake header**: the crash is inside a fake header or stub.

Fix: add a `harness.setup` entry for that type (step 3), or fix the fake.
If your function really must handle that input, it is a real bug after all.

## 8. Keep it running

- Commit `autofuzz.yaml`, not `autofuzz-out/`.
- In CI, `autofuzz run` exits 0 if nothing was found, 1 if something was
  found, 2 or more on an error (missing tool, compile error).
- If your code has known bugs you do not fix yet, keep a list of them like
  `examples/ringbuf_cli/expected_findings.txt`; this repository's
  `make test` compares the findings with such lists
  (`Tests/check_results.py`).
- AutoFuzz skips functions that cannot run on a PC (inline asm, fixed
  register addresses, endless loops) and lists them in
  `autofuzz-out/gen/skipped.txt`.

More: [HOW_IT_WORKS.md](HOW_IT_WORKS.md) (one function step by step,
glossary), [CONFIG.md](CONFIG.md) (every key), [ARCHITECTURE.md](ARCHITECTURE.md).
