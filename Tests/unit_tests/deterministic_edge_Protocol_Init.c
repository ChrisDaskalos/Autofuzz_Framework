#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>
#include <limits.h>
#include <stdint.h>
#include <string.h>

#include "test_common.h"


static void test_Protocol_Init_edge_1(void **state) {
    (void)state;
    ProtocolContext ctx;
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;

    /* Call target function */
    Protocol_Init(&ctx);

    /* Test passes if no crash/assertion */
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_Protocol_Init_edge_1),
    };
    return cmocka_run_group_tests_name("deterministic_edge_Protocol_Init", tests, NULL, NULL);
}
