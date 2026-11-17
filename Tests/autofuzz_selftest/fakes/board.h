/* AutoFuzz self-test: a fake board header (used through fake_include_dirs).
 * The functions are only declared; AutoFuzz generates stubs for them. */
#ifndef BOARD_H
#define BOARD_H

#include <stdint.h>

#define LED_REG_ADDR  0x40010810u        /* a register address on the board */

void        board_poll(void);
int         board_ready(void);
const char *board_name(void);            /* stub returns NULL -> stubgen warns */

/* A helper defined in the fake header. It does not check b, so a crash
 * here is the fault of the fake, not of the code under test:
 * AutoFuzz marks it NEEDS REVIEW (top frame in fake header). */
static inline int board_div(int a, int b)
{
    return a / b;
}

#endif
