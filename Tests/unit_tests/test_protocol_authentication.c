#include "test_common.h"

static void test_authentication_success(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);
    // Use the correct password defined in protocol_defs.h
    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    assert_int_equal(ctx.authenticated, 1);
    assert_int_equal(ctx.state, STATE_MENU);
}

static void test_authentication_failure(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);
    Protocol_ProcessCommand(&ctx, "wrongpass");
    assert_int_equal(ctx.authenticated, 0);
    assert_int_equal(ctx.state, STATE_MENU);
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_authentication_success),
        cmocka_unit_test(test_authentication_failure),
    };
    return cmocka_run_group_tests(tests, NULL, NULL);
}
