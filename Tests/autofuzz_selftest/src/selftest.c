/*
 * AutoFuzz self-test.
 *
 * A tiny C file with one example of each case that AutoFuzz must handle.
 * `make test` checks the result against Tests/expected_findings.txt:
 *   - the 3 functions marked SKIP are reported as SKIPPED with the reason;
 *   - the other functions are tested and find nothing;
 *   - board_name() gets a stub that returns NULL, and a warning;
 *   - first_item() gets a zero-filled int instead of NULL and finds nothing;
 *   - sum3() reads 3 ints, but the test passed ONE zero-filled int:
 *     REVIEW (zero-filled argument), not a firmware bug;
 *   - sensor_value() gets NULL (struct sensor is opaque in selftest.h, so
 *     the test cannot create one) and crashes only because of that:
 *     REVIEW (NULL argument), not a firmware bug;
 *   - ratio() crashes inside the fake header board.h:
 *     REVIEW (top frame in fake header), not a firmware bug.
 */
#include <stddef.h>
#include "selftest.h"
#include "board.h"

/* Tested: no finding (all values are checked before the sum). */
int add_small(int a, int b)
{
    if (a < -100 || a > 100 || b < -100 || b > 100)
        return 0;
    return a + b;
}

/* Tested: an endless loop WITH a break is not skipped. */
int wait_ready(int tries)
{
    while (1) {
        if (board_ready())
            break;
        if (tries <= 0 || tries > 10)
            break;
        tries--;
    }
    return tries;
}

/* Tested: calls a stub that returns a pointer. */
int has_name(void)
{
    return board_name() != NULL;
}

/* Tested: the test has no setup for `const int *`, so it passes a
 * zero-filled int. Reading items[0] is fine. */
int first_item(const int *items)
{
    return items[0];
}

/* Tested: the zero-filled int is only one int; items[1] is past it. */
int sum3(const int *items)
{
    return items[0] + items[1] + items[2];
}

/* Complete here, opaque in selftest.h. */
struct sensor {
    int value;
};

/* Tested: the test cannot create a struct sensor, so it passes NULL. */
int sensor_value(const struct sensor *s)
{
    return s->value;
}

/* Tested: the crash (b == 0) happens in the fake header. */
int ratio(int a, int b)
{
    return board_div(a, b);
}

/* SKIP: register access (an integer constant cast to a pointer). */
void led_on(void)
{
    *(volatile uint32_t *)LED_REG_ADDR = 1u;
}

/* SKIP: inline assembly. */
void cpu_nop(void)
{
    __asm__ volatile ("nop");
}

/* SKIP: never returns. */
void run_forever(void)
{
    for (;;) {
        board_poll();
    }
}
