#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>
#include <limits.h>
#include <stdint.h>
#include <string.h>

#include "test_common.h"

static char * a1_vals[] = { " ", "WRONG", "\n", "unlock", "3", "(181,5,186)", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "\xff\xff", "2", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "\r", "(255,1,0)" };
#define a1_vals_LEN (sizeof(a1_vals)/sizeof(a1_vals[0]))

static void test_Protocol_ProcessCommand_edge_1(void **state) {
    (void)state;
    ProtocolContext ctx;
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;
    char * a1 = " ";

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
    char * a1 = "WRONG";

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
    char * a1 = "\n";

    /* Call target function */
    Protocol_ProcessCommand(&ctx, a1);

    /* Test passes if no crash/assertion */
}

static void test_Protocol_ProcessCommand_edge_4(void **state) {
    (void)state;
    ProtocolContext ctx;
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;
    char * a1 = "unlock";

    /* Call target function */
    Protocol_ProcessCommand(&ctx, a1);

    /* Test passes if no crash/assertion */
}

static void test_Protocol_ProcessCommand_edge_5(void **state) {
    (void)state;
    ProtocolContext ctx;
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;
    char * a1 = "3";

    /* Call target function */
    Protocol_ProcessCommand(&ctx, a1);

    /* Test passes if no crash/assertion */
}

static void test_Protocol_ProcessCommand_edge_6(void **state) {
    (void)state;
    ProtocolContext ctx;
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;
    char * a1 = "(181,5,186)";

    /* Call target function */
    Protocol_ProcessCommand(&ctx, a1);

    /* Test passes if no crash/assertion */
}

static void test_Protocol_ProcessCommand_edge_7(void **state) {
    (void)state;
    ProtocolContext ctx;
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;
    char * a1 = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";

    /* Call target function */
    Protocol_ProcessCommand(&ctx, a1);

    /* Test passes if no crash/assertion */
}

static void test_Protocol_ProcessCommand_edge_8(void **state) {
    (void)state;
    ProtocolContext ctx;
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;
    char * a1 = "\xff\xff";

    /* Call target function */
    Protocol_ProcessCommand(&ctx, a1);

    /* Test passes if no crash/assertion */
}

static void test_Protocol_ProcessCommand_edge_9(void **state) {
    (void)state;
    ProtocolContext ctx;
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;
    char * a1 = "2";

    /* Call target function */
    Protocol_ProcessCommand(&ctx, a1);

    /* Test passes if no crash/assertion */
}

static void test_Protocol_ProcessCommand_edge_10(void **state) {
    (void)state;
    ProtocolContext ctx;
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;
    char * a1 = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";

    /* Call target function */
    Protocol_ProcessCommand(&ctx, a1);

    /* Test passes if no crash/assertion */
}

static void test_Protocol_ProcessCommand_edge_11(void **state) {
    (void)state;
    ProtocolContext ctx;
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;
    char * a1 = "\r";

    /* Call target function */
    Protocol_ProcessCommand(&ctx, a1);

    /* Test passes if no crash/assertion */
}

static void test_Protocol_ProcessCommand_edge_12(void **state) {
    (void)state;
    ProtocolContext ctx;
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;
    char * a1 = "(255,1,0)";

    /* Call target function */
    Protocol_ProcessCommand(&ctx, a1);

    /* Test passes if no crash/assertion */
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_Protocol_ProcessCommand_edge_1),
        cmocka_unit_test(test_Protocol_ProcessCommand_edge_2),
        cmocka_unit_test(test_Protocol_ProcessCommand_edge_3),
        cmocka_unit_test(test_Protocol_ProcessCommand_edge_4),
        cmocka_unit_test(test_Protocol_ProcessCommand_edge_5),
        cmocka_unit_test(test_Protocol_ProcessCommand_edge_6),
        cmocka_unit_test(test_Protocol_ProcessCommand_edge_7),
        cmocka_unit_test(test_Protocol_ProcessCommand_edge_8),
        cmocka_unit_test(test_Protocol_ProcessCommand_edge_9),
        cmocka_unit_test(test_Protocol_ProcessCommand_edge_10),
        cmocka_unit_test(test_Protocol_ProcessCommand_edge_11),
        cmocka_unit_test(test_Protocol_ProcessCommand_edge_12),
    };
    return cmocka_run_group_tests_name("deterministic_edge_Protocol_ProcessCommand", tests, NULL, NULL);
}
