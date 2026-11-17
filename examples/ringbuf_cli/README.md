# ringbuf_cli – a second example project for AutoFuzz

A small project in plain C (no microcontroller, no HAL). It shows that
AutoFuzz is not tied to the servo firmware in this repository.

```
examples/ringbuf_cli/
├── autofuzz.yaml           what AutoFuzz should test (see docs/CONFIG.md)
├── expected_findings.txt   what `make test` expects AutoFuzz to find
├── include/
│   ├── ringbuf.h           ring buffer (FIFO) of bytes
│   └── cli.h               text commands: push, pop, peek, fill, count, clear
└── src/
    ├── ringbuf.c
    └── cli.c
```

`cli_run("fill 8;pop;push 42")` runs commands on an empty ring buffer of 8
bytes. The commands are listed in `include/cli.h`.

## The bug (added on purpose)

`src/ringbuf.c`, in `ringbuf_push`:

```c
    rb->data[rb->head] = value;     /* line 34 */
    rb->head++;
    if (rb->head > rb->cap) {       /* BUG (on purpose): must be >= */
        rb->head = 0;
    }
```

`head` should go back to 0 when it reaches `cap` (8). With `>` it becomes
8 first. When the buffer is full, push is refused, so nothing goes wrong
yet. But after one `pop` there is room again, and the next `push` writes
`data[8]`: one byte past the end of the 8-byte array (an off-by-one).

AutoFuzz finds it in the edge test of `cli_run`, with the seed script from
`autofuzz.yaml` that fills the buffer, pops one byte and pushes one:

```
=== EDGE: deterministic_edge_cli_run === FOUND SOMETHING
    SUMMARY: AddressSanitizer: global-buffer-overflow .../examples/ringbuf_cli/src/ringbuf.c:34:24 in ringbuf_push
```

The fix is `if (rb->head >= rb->cap)`. Do not fix it here: `make test`
expects this finding (`expected_findings.txt`).

## Run it

From this folder:

```bash
PYTHONPATH=../.. python3 -m autofuzz run       # or `autofuzz run` after `pip install .`
```

A step-by-step walk-through is in [docs/GETTING_STARTED.md](../../docs/GETTING_STARTED.md).
