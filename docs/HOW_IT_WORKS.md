# How AutoFuzz works

This page follows **one function** through the whole tool, from the C code to
the error message. The words in *italics* are explained in the
[glossary](#glossary) at the end.

The function is `ComputeChecksumFromNumbers`. It has a real bug (bug 2 in
[FINDINGS.md](FINDINGS.md)). The example uses the legacy copy in
`Tests/legacy_thesis/`, because that is what AutoFuzz reads today.

## The 7 stages

```
1. source code  →  2. scanner  →  3. edge values  →  4. generated files
   →  5. compile with sanitizers  →  6. run  →  7. error message
```

---

### 1. Source code

`Tests/legacy_thesis/test_common.c`, lines 160–163:

```c
uint8_t ComputeChecksumFromNumbers(int a, int b)
{
    return (uint8_t)(a + b); /* keep UB so UBSan flags it */
}
```

The problem: if `a + b` is bigger than the largest `int` (2147483647), the
result is **undefined behaviour** in C. The program may do anything.

The real firmware has the same code at `Core/Src/protocol.c:159`.

### 2. Scanner

`make build` runs `autofuzz build --config Tests/legacy_thesis/autofuzz.yaml`.
That file says which C file to read (`sources: [test_common.c]`), where its
headers are, and which extra test strings to use (see [CONFIG.md](CONFIG.md)).

`autofuzz/scanner.py` asks **libclang** (the C parser of clang) to read
`test_common.c`. It keeps every function that is defined in that file and
is not `static`.

`ComputeChecksumFromNumbers` passes. It has two parameters, both
of type `int`.

For each parameter, the scanner also looks inside the function for useful
numbers: comparisons (`if (x > 165)`), `switch` cases, and literals. This
function has none, so only the default values are used.

### 3. Edge values

The default values for each type come from a rule in `autofuzz/config.py`
(based on the size of the type). For `int` they
are the "dangerous" numbers: the smallest, the largest, and numbers near 0
and near the 16-bit limits:

```
-2147483648, -2147483647, -32768, -2, -1, 0, 1, 2,
32767, 32768, 65535, 2147483646, 2147483647
```

`generator.py` sorts the values and keeps at most 12 per parameter
(`limits.edge_cap` in the YAML), spread from the smallest to the largest:

```c
static int a0_vals[] = { -2147483648, -2147483647, -32768, -2, -1, 0, 2,
                         32767, 32768, 65535, 2147483646, 2147483647 };
```

Two parameters with 12 values each gives 144 pairs. That is too many, so
for two parameters the generator picks 4 values each (the smallest, the
largest, a small positive number, and one more), makes all 16 pairs, and
keeps the 12 pairs most likely to overflow (extreme values first).

### 4. Generated files

Two files are written for the function.

**`deterministic_edge_ComputeChecksumFromNumbers.c`**: an *edge test*. It
is a *CMocka* program with 12 tests, one per pair. Test 1:

```c
static void test_ComputeChecksumFromNumbers_edge_1(void **state) {
    (void)state;
    int a0 = (int)-2147483648;
    int a1 = (int)-2147483648;

    /* Call target function */
    ComputeChecksumFromNumbers(a0, a1);

    /* Test passes if no crash/assertion */
}
```

The test does not check the return value. It only checks that nothing bad
happens. The *sanitizer* decides what "bad" means.

**`random_fuzz_ComputeChecksumFromNumbers.c`**: a *harness* for *libFuzzer*.
libFuzzer gives it random bytes. The harness turns the first 8 bytes into
two `int` values and calls the function:

```c
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (!data || size < 8) return 0;

    int32_t a0;
    memcpy(&a0, data + 0, sizeof(int32_t));
    int32_t a1;
    memcpy(&a1, data + 4, sizeof(int32_t));

    /* Call target function with fuzzer-derived inputs */
    ComputeChecksumFromNumbers(a0, a1);
    return 0;
}
```

The generated files are the same every time (`make check-determinism`
checks this). They are written to `Tests/legacy_thesis/autofuzz-out/gen/`,
which is not stored in git; `make build` writes them again.

### 5. Compile with sanitizers

`autofuzz/runner.py` compiles each file together with `test_common.c`,
using clang (no Makefile needed). Before that, it checks that clang,
CMocka and libFuzzer are installed:

| Program | Sanitizer flags |
|---|---|
| edge test | `-fsanitize=address,undefined` |
| fuzzer | `-fsanitize=address,undefined,integer -fsanitize=fuzzer` |

The *sanitizers* add checks to the machine code. For example, before every
`a + b` there is now a check: "does the result fit in an `int`?"

### 6. Run

`make test` runs every program (it calls `autofuzz run`). You can also run
them one by one:

```bash
make build
cd Tests/legacy_thesis/autofuzz-out
./bin/deterministic_edge_ComputeChecksumFromNumbers
./bin/random_fuzz_ComputeChecksumFromNumbers -max_total_time=10 corpus/random_fuzz_ComputeChecksumFromNumbers
```

### 7. Error message

**Edge test**: test 1 adds `-2147483648 + -2147483648`. The real output,
copied from `Tests/results/edge.log` (long paths shortened):

```
[==========] deterministic_edge_ComputeChecksumFromNumbers: Running 12 test(s).
[ RUN      ] test_ComputeChecksumFromNumbers_edge_1
.../Tests/legacy_thesis/test_common.c:162:24: runtime error: signed integer overflow: -2147483648 + -2147483648 cannot be represented in type 'int'
    #0 0x4c66b6 in ComputeChecksumFromNumbers .../Tests/legacy_thesis/test_common.c:162:24
    #1 0x4c33d4 in test_ComputeChecksumFromNumbers_edge_1 .../Tests/legacy_thesis/autofuzz-out/gen/deterministic_edge_ComputeChecksumFromNumbers.c:22:5
    #2 0x7f70bc434f30 in cmocka_run_one_test_or_fixture (/usr/local/lib/libcmocka.so.0+0x8f30)
```

Read it like this:

- `.../test_common.c:162:24`: file, line and column of the bug.
- `signed integer overflow: -2147483648 + -2147483648`: what went wrong, and
  the values.
- `#0`, `#1`, …: the *stack trace*. `#0` is the function where the bug is;
  `#1` is the test that called it.

**Fuzzer**: libFuzzer finds random values that overflow in less than one
second. The real output, from `Tests/results/fuzz.log` (long paths shortened):

```
.../Tests/legacy_thesis/test_common.c:162:24: runtime error: signed integer overflow: 2140273916 + 235802126 cannot be represented in type 'int'
    #0 0x5516b6 in ComputeChecksumFromNumbers .../Tests/legacy_thesis/test_common.c:162:24
    #1 0x54ddfb in LLVMFuzzerTestOneInput .../Tests/legacy_thesis/autofuzz-out/gen/random_fuzz_ComputeChecksumFromNumbers.c:20:5
    ...
SUMMARY: UndefinedBehaviorSanitizer: signed-integer-overflow .../Tests/legacy_thesis/test_common.c:162:24 in
MS: 1 ChangeBit-; base unit: 80e9dd3300d6fd2e9eeeaf169db82de72b0f1ab5
0xfc,0xfc,0x91,0x7f,0xe,0xe,0xe,0xe,
\xfc\xfc\x91\x7f\x0e\x0e\x0e\x0e
artifact_prefix='crashes/'; Test unit written to crashes/crash-15e19b07df8b5fd68aab2f64efdcc23ed92f74d8
```

The 8 bytes are the input: `fc fc 91 7f` is `2140273916` and
`0e 0e 0e 0e` is `235802126` (little-endian). The input is saved in
`autofuzz-out/crashes/`. To run it again:

```bash
cd Tests/legacy_thesis/autofuzz-out
./bin/random_fuzz_ComputeChecksumFromNumbers crashes/crash-<id>
```

(The values change on every run, because the fuzzer is random. The bug is
always the same.)

### And then: check the results

`Tests/check_results.py` reads all logs and turns each `SUMMARY:` line into
one finding:

```
edge  deterministic_edge_ComputeChecksumFromNumbers  UBSAN signed-integer-overflow test_common.c:162
fuzz  random_fuzz_ComputeChecksumFromNumbers         UBSAN signed-integer-overflow test_common.c:162
```

Both lines are in `Tests/expected_findings.txt`, so `make test` says
`All results as expected`. If the bug is fixed, these lines disappear, and
you must delete them from the expected list too.

---

## Glossary

| Word | Meaning |
|---|---|
| **harness** | A small C program that calls the function under test. A fuzz harness has the function `LLVMFuzzerTestOneInput(data, size)` and turns the bytes into arguments. |
| **corpus** | A folder of inputs for a fuzzer. libFuzzer starts from these inputs and saves new ones that reach new code. Here: `autofuzz-out/corpus/<fuzzer>/`, and `Tests/fuzz_manual/corpus/` (seeds stored in git). |
| **dictionary** | A list of words (for example `"1234"` or `","`) that the fuzzer puts into its inputs. It helps the fuzzer get past checks like a password. Here: `Tests/fuzz_manual/*.dict`. |
| **sanitizer** | A compiler option that adds checks to the program. **AddressSanitizer** (ASan) finds memory errors, for example reading past the end of a buffer. **UndefinedBehaviorSanitizer** (UBSan) finds undefined behaviour, for example signed integer overflow. Each prints the file and line. |
| **libFuzzer** | A fuzzer built into clang (`-fsanitize=fuzzer`). It calls the harness millions of times with changed inputs, and stops when the program crashes or a sanitizer reports an error. |
| **CMocka** | A small unit test library for C. Each test is a C function; CMocka runs them and prints `[  PASSED  ]` or `[  FAILED  ]`. |
| **stub** | A fake version of a function, for the PC. For example `HAL_UART_Transmit` on the PC does not send anything; it only returns `HAL_OK`. |
| **edge test** | A test that calls a function with boundary values: the smallest and largest numbers, 0, -1, an empty string, a very long string. Many bugs happen at these values. |
| stack trace | The list of functions that were running when the error happened. `#0` is the innermost one. |
| undefined behaviour | Code whose result the C standard does not define, for example `INT_MAX + 1`. The compiler may produce any result. |
