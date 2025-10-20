/**
 * @file test_protocol_authentication.c
 * @brief Unit tests validating the authentication mechanism of the protocol implementation.
 *
 * @details
 * This file contains CMocka-based unit tests for verifying the behavior of the
 * authentication logic within the protocol. It tests both successful and failed
 * authentication scenarios by:
 *   - Initializing a ProtocolContext.
 *   - Issuing the valid password (PROTOCOL_PASSWORD) or an incorrect one.
 *   - Asserting the expected `authenticated` flag and `state` transitions.
 *
 * Tests included:
 *   - test_authentication_success: ensures correct password sets `authenticated = 1`
 *     and advances to STATE_MENU.
 *   - test_authentication_failure: ensures wrong password leaves
 *     `authenticated = 0` but still advances to STATE_MENU.
 *
 * All tests are registered and run via cmocka_run_group_tests in main().
 */

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
