# Findings

This page lists what the tests find, and says for each finding if it is in the
**real firmware** (`Core/Src`) or only in the **legacy copy**
(`Tests/legacy_thesis/test_common.c`).

Why there are two places: the thesis version of AutoFuzz tested a PC copy of the
firmware logic (`test_common.c`), not the firmware files themselves. The copy is
close to the firmware, but not the same. Since milestone M4, AutoFuzz also tests
the real `Core/Src/protocol.c` and `servo.c` (the root `autofuzz.yaml`), compiled
**without** `UNIT_TEST`, like on the board. The hand-written fuzzers in
`Tests/fuzz_manual/` also link the real files (with `UNIT_TEST`).

## Summary

| Finding | In the legacy copy | In the real firmware | Found by AutoFuzz on the real code (M4) | Status |
|---|---|---|---|---|
| Bug 1: stack buffer overflow (command of 1024+ characters) | yes | **no** | no (as expected) | only in the copy |
| Bug 2: signed integer overflow in `angle + step` | yes (`test_common.c:162`, and `test_common.c:94`) | **yes** (`Core/Src/protocol.c:159`) | **yes**, also through `Protocol_ProcessCommand` | **real bug** |
| `assert` in `Servo_Ramp` for step 0 or step > 45 | – (the copy has no assert) | **yes** (`Core/Src/servo.c:40`) | **yes** | **real behaviour** |
| 4 failing unit tests (spaces around `B`, a 4th field, step 0, negative step) | yes | **yes** | – (unit tests only) | **real behaviour** |
| DMA length overflow in `fuzz_uart_dma` (old) | – | **no** | – (`main.c` is not covered) | was a harness mistake, fixed |
| `main.c` does not compile: `dmaBuffer[64]` vs `dmaBuffer[1024]` | – | **yes** (`Core/Inc/main.h:39`, `protocol_defs.h:10`) | – (seen by the compiler, see below) | **to check in CubeIDE** |

Since the fuzzer fix in 1.0 (see [below](#the-fuzzers-were-blind-fixed-in-10)),
the generated fuzzers find more. No new bug was found in the real firmware.

The full list that `make test` checks is in
[`Tests/expected_findings.txt`](../Tests/expected_findings.txt) (and, for the
second example project, in
[`examples/ringbuf_cli/expected_findings.txt`](../examples/ringbuf_cli/expected_findings.txt)).

---

## Bug 1: stack buffer overflow (legacy copy only)

**What happens in the copy.** `Protocol_ProcessCommand` in
`Tests/legacy_thesis/test_common.c` copies the command into
`char buf[DMA_BUFFER_SIZE]` (1024 bytes, line 117). If the command has 1024 or
more characters and no line end, all 1024 bytes are used and there is no `\0`
at the end. Then `strtok`/`strcmp` read past the end of `buf`.

**Found by:** `deterministic_edge_Protocol_ProcessCommand` (always), and
sometimes `random_fuzz_Protocol_ProcessCommand` (marked `maybe` in the expected list).

```
==20353==ERROR: AddressSanitizer: stack-buffer-overflow on address 0x7ffd8cc962e0 ...
SUMMARY: AddressSanitizer: stack-buffer-overflow (.../deterministic_edge_Protocol_ProcessCommand+0x4304e0) in strtok
```

**Why it is not in the real firmware.** In `Core/Src/main.c`, `ProcessUartData`
copies the DMA data into `char lineBuffer[DMA_BUFFER_SIZE + 1] = {0}` and then
writes `lineBuffer[length] = '\0'` (line 83 onwards). The DMA length is at most
`DMA_BUFFER_SIZE` (1024), so there is always room for the `\0`. The string
that reaches `Protocol_ProcessCommand` always ends with `\0`.

The comment in the copy says the missing `\0` was kept on purpose, to show what
would happen without it. So this finding shows that the tool works, but it is
**not a firmware bug**.

---

## Bug 2: signed integer overflow in the checksum (real)

**Code.**

```c
/* Core/Src/protocol.c:157-160 */
uint8_t ComputeChecksumFromNumbers(int angle, int step)
{
    return (uint8_t)(angle + step);
}
```

`angle` and `step` come from `atoi()` on the user's text. If their sum is bigger
than `INT_MAX` (or smaller than `INT_MIN`), the addition is **undefined
behaviour** in C.

**What it does on the board (in practice).** The sum wraps around. Example
input over UART: password `1234`, menu `1`, then `2147483647,1,0`. The sum wraps
to `-2147483648`, whose low byte is `0`, so the checksum `0` is accepted. The
angle is then limited to 165 and the command is queued. So a wrong command can
pass the checksum check.

**How to fix it (not done, the finding is kept on purpose).** Check the ranges
of `angle` and `step` before the addition, or add as `unsigned`:
`return (uint8_t)((unsigned)angle + (unsigned)step);`

**Found by:**

| Test | Where | Output |
|---|---|---|
| `test_manual_overflow` (hand-written demo) | copy, `test_common.c:162` | `signed integer overflow: 2147483647 + 2147483647` |
| `deterministic_edge_ComputeChecksumFromNumbers` (generated) | copy, `test_common.c:162` | `signed integer overflow: -2147483648 + -2147483648` |
| `random_fuzz_ComputeChecksumFromNumbers` (generated, < 1 s) | copy, `test_common.c:162` | random values, for example `1760837426 + 536933439` |
| `Tests/fuzz_manual`: `fuzz_protocol_cmd`, `fuzz_protocol_session` | **real**, `Core/Src/protocol.c:159` | `signed integer overflow: 2147483647 + 1` |
| AutoFuzz `deterministic_edge_ComputeChecksumFromNumbers`, `random_fuzz_ComputeChecksumFromNumbers` (stage `real-edge`/`real-fuzz`) | **real**, `Core/Src/protocol.c:159` | `signed integer overflow` |
| AutoFuzz `deterministic_edge_Protocol_ProcessCommand` (seed `(2147483647,1,0)` from `autofuzz.yaml`) | **real**, `Core/Src/protocol.c:159` | the same bug, reached through the real command parser |

Real output from `fuzz_protocol_cmd`:

```
../../Core/Src/protocol.c:159:28: runtime error: signed integer overflow: 2147483647 + 1 cannot be represented in type 'int'
SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior ../../Core/Src/protocol.c:159:28 in
```

---

## The 4 failing unit tests (real behaviour)

The hand-written unit tests in `Tests/legacy_thesis/test_*.c` describe how the
protocol **should** behave. Four of them fail, because the code does something
else. The same logic is in the real `Core/Src/protocol.c`, so this is real
firmware behaviour.

| Test | Input | The test expects | The code does |
|---|---|---|---|
| `test_state_machine_cancellation_with_whitespace` | `"   B   "` while the servo moves | cancel | Ignores it. Only exactly `B` or `b` cancels; spaces are not removed. |
| `test_servo_command_extra_fields` | `90,5,95,100` | reject | Accepts it. Only the first 3 fields are read; the 4th is ignored. |
| `test_servo_command_zero_step` | `90,0,90` | reject | Accepts it. There is no check for step = 0. |
| `test_servo_command_negative_step` | `90,-5,85` | reject | Accepts it. `-5` is stored as `uint8_t`, so it becomes `251`, and the checksum still matches. |

**Step 0 and a negative step on the board.** The command is queued, and later
the main loop calls `Servo_Ramp`. In the firmware build (without `UNIT_TEST`)
`Core/Src/servo.c` has:

```c
assert(step != 0 && step <= SERVO_MAX_STEP);
```

So the firmware stops at the `assert` (when asserts are on, that is, `NDEBUG` is not
defined). The hand-written fuzzers and the legacy copy use `-DUNIT_TEST`, and there
`Servo_Ramp` just returns, so they do not stop here.

AutoFuzz on the real code (M4) compiles `servo.c` **without** `UNIT_TEST`, so it
reaches the assert. Both `deterministic_edge_Servo_Ramp` and `random_fuzz_Servo_Ramp`
report:

```
servo.c:40: void Servo_Ramp(uint8_t *, uint8_t, uint8_t): Assertion `step != 0 && step <= SERVO_MAX_STEP' failed.
```

`Tests/check_results.py` records it as `ASSERT servo.c:40 in Servo_Ramp`.

Whether these 4 behaviours are bugs or acceptable is a design choice. The tests
record that the code does not do what the tests expect.

---

## Not a bug: DMA length in `fuzz_uart_dma`

Earlier versions of `Tests/fuzz_manual/fuzz_uart_dma.c` reported a `memcpy`
overflow and a wrap-around in `DMA_BUFFER_SIZE - remain`. The harness gave the
DMA counter any 32-bit value. On the STM32F103 the counter starts at the buffer
size (1024) and only counts down, so the firmware can only read 0 to 1024. With
realistic values there is no finding. This was a mistake in the harness, and
it is fixed (commit `267a8b7`).

A check `if (remain > DMA_BUFFER_SIZE)` in `main.c` would still be good
defensive code.

---

## AutoFuzz on the real firmware (M4)

The root [`autofuzz.yaml`](../autofuzz.yaml) points AutoFuzz at
`Core/Src/protocol.c` and `Core/Src/servo.c`:

- They are compiled **without** `-DUNIT_TEST`, so the code is the same as on the board.
- `#include "stm32f1xx_hal.h"` finds the fake HAL in `autofuzz/fakes/stm32f1_hal/`
  (types and declarations only).
- AutoFuzz generates stubs for what the files use but do not define:
  `HAL_UART_Transmit`, `HAL_TIM_PWM_Start`, `HAL_Delay`, `huart2`, `htim2`
  (`autofuzz-out/stubs/stubs.c`).

Result, as this page predicted before M4: bug 2 and the `Servo_Ramp` assert are
found in the real code. Bug 1 is **not** found. No function is skipped, and no
finding needs review.

A finding is marked **needs review** (`REVIEW (...)` in the results), and is not
counted as a firmware bug, when the test may have caused it:

- its top stack frame is in a generated harness, a stub or a fake header; or
- it is a NULL-pointer crash, and the test passed NULL for a pointer argument
  (only for types the test cannot create: `void *`, an opaque struct); or
- the test passed a zero-filled object for a pointer argument (a pointer
  parameter with no `harness.setup` entry), and the function read past it or
  hit a NULL pointer inside it.

`Tests/autofuzz_selftest/` shows all three cases. The legacy and real configs
give every pointer parameter a `harness.setup`, so none of their findings
depend on this.

---

## Found while doing M4: `main.c` and `DMA_BUFFER_SIZE`

`DMA_BUFFER_SIZE` is defined twice, with different values:

- `Core/Inc/main.h:39`: `#define DMA_BUFFER_SIZE 64`. `main.h` also declares
  `extern uint8_t dmaBuffer[DMA_BUFFER_SIZE];`, so the declaration says 64.
- `Core/Inc/protocol_defs.h:10`: `#define DMA_BUFFER_SIZE 1024`.

`main.c` includes `main.h` first and `protocol.h` after it. Then line 60,
`uint8_t dmaBuffer[DMA_BUFFER_SIZE];`, defines the buffer with 1024 bytes.

The PC compilers reject this, using the real HAL headers and the `.ioc` defines:

```
clang: Core/Src/main.c:60:9: error: redefinition of 'dmaBuffer' with a different type: 'uint8_t [1024]' vs 'uint8_t [64]'
gcc:   Core/Src/main.c:60:9: error: conflicting types for 'dmaBuffer'
```

`protocol.c` and `servo.c` compile, with only a warning that the macro is
redefined. They do not use `dmaBuffer`.

**To check in STM32CubeIDE:** does the project build with these files? If it
does, the IDE project must differ from git. If it does not, one value of
`DMA_BUFFER_SIZE` should be removed. `Core/` was not changed in M4.

---

## The fuzzers were blind (fixed in 1.0)

**What was wrong.** A libFuzzer fuzzer learns which inputs reach new code
through *coverage instrumentation*. AutoFuzz compiled the test harness with
`-fsanitize=fuzzer`, but the **code under test** (`sources`) without
`-fsanitize=fuzzer-no-link`. So libFuzzer saw only the few branches of the
harness (`cov: 4` in every log) and mutated its inputs blindly. Since 1.0,
`autofuzz/runner.py` compiles the sources of a fuzzer with
`-fsanitize=fuzzer-no-link`.

**The thesis version had the same problem.** In `thesis-v1`,
`Tests/unit_tests/Makefile` compiled the code under test with
`FUZZ_CFLAGS = $(COMMON) $(SAN_FUZZ)`, without `-fsanitize=fuzzer-no-link`,
and only the link step had `-fsanitize=fuzzer`. So the thesis fuzzing
results of the *generated* fuzzers came from blind, random inputs. The
*hand-written* fuzzers in `Tests/fuzz_manual/` were not affected: they compile
every file with `-fsanitize=fuzzer`.

**What changed (10 s per fuzzer, 5 runs):**

| Fuzzer | Before the fix | After the fix |
|---|---|---|
| real `random_fuzz_Protocol_ProcessCommand` | Bug 2 (`protocol.c:159`) only sometimes | Bug 2 in 5 of 5 runs |
| legacy `random_fuzz_Protocol_ProcessCommand` | Bug 1 only sometimes | always a finding: Bug 1 (3 runs) or Bug 2 at `test_common.c:94` (2 runs) |
| ringbuf `random_fuzz_cli_run`, `random_fuzz_cli_execute` | never, also not in 300 s with a dictionary | the off-by-one in about 1 s, 5 of 5 runs |

**New finding (legacy copy only): Bug 2 at `test_common.c:94`.** The copy's
`Protocol_ProcessCommand` checks the checksum with
`if ((uint8_t)(angle + step) != (uint8_t)cks)`, so a large angle and step
overflow `int` there too:

```
test_common.c:94:25: runtime error: signed integer overflow: 1260588259 + 1720980707 cannot be represented in type 'int'
```

Input (31 bytes, found by the fuzzer): `5555555555\t\t,57555555555,\t55555`
(hex `35 35 35 35 35 35 35 35 35 35 09 09 2c 35 37 35 35 35 35 35 35 35 35 35 2c 09 35 35 35 35 35`).
Repeat it: write these bytes to a file and run
`Tests/legacy_thesis/autofuzz-out/bin/random_fuzz_Protocol_ProcessCommand <file>`.
The real firmware does this sum only in `ComputeChecksumFromNumbers`
(`protocol.c:159`, already Bug 2), so it has no second place. No new finding
appeared in the real firmware.

---

## The second project: `examples/ringbuf_cli` (M5)

Not part of the firmware. A small plain-C project with **one bug added on
purpose**, to show that AutoFuzz works on other code too: the wrap check in
`ringbuf_push` uses `>` instead of `>=`, so after "fill, pop one, push one" it
writes one byte past the 8-byte buffer.

| Finding | Found by | Expected list |
|---|---|---|
| `ASAN global-buffer-overflow ringbuf.c:34 in ringbuf_push` | `deterministic_edge_cli_run`, and both fuzzers `random_fuzz_cli_run` / `random_fuzz_cli_execute` by themselves (in about 1 s, since the fuzzer fix) | [`examples/ringbuf_cli/expected_findings.txt`](../examples/ringbuf_cli/expected_findings.txt) |

Details: [the example's README](../examples/ringbuf_cli/README.md) and
[GETTING_STARTED.md](GETTING_STARTED.md).

---

## Not covered

AutoFuzz does **not** test `Core/Src/main.c`. That includes the UART/DMA receive
path (`HAL_UART_IdleCallback` → `ProcessUartData` → `Protocol_ProcessCommand`),
`main()`, and the clock, GPIO, timer and UART setup. These need the real
registers (`TIM2`, `USART2`, `huart2.Instance->CR1`, ...), and `main()` never
returns. `main.c` also does not compile at the moment (see above).

The receive path is tested only by the hand-written fuzzer
`Tests/fuzz_manual/fuzz_uart_dma.c`. It uses a **copy** of the DMA idle-callback
logic from `main.c`, so a change in `main.c` must be copied there by hand.

Also not covered: the CubeMX/HAL files in `Drivers/` and `Core/Src/stm32f1xx_*.c`
(library and interrupt code).
