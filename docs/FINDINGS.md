# Findings

This page lists what the tests find, and says for each finding if it is in the
**real firmware** (`Core/Src`) or only in the **legacy copy**
(`Tests/legacy_thesis/test_common.c`).

Why there are two places: the thesis version of AutoFuzz tested a PC copy of the
firmware logic (`test_common.c`), not the firmware files themselves. The copy is
close to the firmware, but not the same. The hand-written fuzzers in
`Tests/fuzz_manual/` link the real `Core/Src/protocol.c` and `servo.c`.

## Summary

| Finding | In the legacy copy | In the real firmware | Status |
|---|---|---|---|
| Bug 1: stack buffer overflow (command of 1024+ characters) | yes | **no** | only in the copy |
| Bug 2: signed integer overflow in `angle + step` | yes (`test_common.c:162`) | **yes** (`Core/Src/protocol.c:159`) | **real bug** |
| 4 failing unit tests (spaces around `B`, a 4th field, step 0, negative step) | yes | **yes** | **real behaviour** |
| DMA length overflow in `fuzz_uart_dma` (old) | – | **no** | was a harness mistake, fixed |

The full list that `make test` checks is in
[`Tests/expected_findings.txt`](../Tests/expected_findings.txt).

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
defined). The PC builds use `-DUNIT_TEST`, and there `Servo_Ramp` just returns,
so the fuzzers do not stop here.

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

## What changes later

From milestone M4 (see [ROADMAP.md](ROADMAP.md)), AutoFuzz will test
`Core/Src` directly. Then bug 2 and the `Servo_Ramp` assert should be found
there too, and bug 1 should **not** be found. That will confirm this page.
