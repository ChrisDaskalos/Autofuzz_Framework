#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>
#include <limits.h>
#include <stdint.h>
#include <string.h>

#include "test_common.h"

static char * a1_vals[] = { "0", "1", "-1" };
#define a1_vals_LEN (sizeof(a1_vals)/sizeof(a1_vals[0]))

static void test_Protocol_ProcessCommand_edge_1(void **state) {
    (void)state;
    ProtocolContext ctx;
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;
    char * a1 = "";
    a1 = a1_vals[0];

    /* Call target function */
    Protocol_ProcessCommand(&ctx, a1);

    /* Test passes if no crash/assertion */
}

static void test_Protocol_ProcessCommand_edge_2(void **state) {
    (void)state;
    ProtocolContext ctx;
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;
    char * a1 = "";
    a1 = a1_vals[1];

    /* Call target function */
    Protocol_ProcessCommand(&ctx, a1);

    /* Test passes if no crash/assertion */
}

static void test_Protocol_ProcessCommand_edge_3(void **state) {
    (void)state;
    ProtocolContext ctx;
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;
    char * a1 = "";
    a1 = a1_vals[2];

    /* Call target function */
    Protocol_ProcessCommand(&ctx, a1);

    /* Test passes if no crash/assertion */
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_Protocol_ProcessCommand_edge_1),
        cmocka_unit_test(test_Protocol_ProcessCommand_edge_2),
        cmocka_unit_test(test_Protocol_ProcessCommand_edge_3),
    };
    return cmocka_run_group_tests_name("deterministic_edge_Protocol_ProcessCommand", tests, NULL, NULL);
}
