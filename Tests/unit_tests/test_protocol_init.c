/**
 * @file test_protocol_init.c
 * @brief Unit test for the Protocol_Init function.
 *
 * @details
 * This file provides a CMocka unit test verifying that Protocol_Init correctly
 * initializes a ProtocolContext structure with all expected default values:
 *   - authenticated      = 0
 *   - current_servo_angle = SERVO_DEFAULT_ANGLE
 *   - state              = STATE_MENU
 *   - diagnostic_info    = "AWAITING PASSWORD."
 *   - pendingTargetAngle = 0
 *   - pendingStep        = 0
 *   - commandPending     = 0
 *
 * Registered and run via cmocka_run_group_tests in main().
 */
#include "test_common.h"

static void test_protocol_init(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);
    assert_int_equal(ctx.authenticated, 0);
    assert_int_equal(ctx.current_servo_angle, SERVO_DEFAULT_ANGLE);
    assert_int_equal(ctx.state, STATE_MENU);
    assert_string_equal(ctx.diagnostic_info, "AWAITING PASSWORD.");
    assert_int_equal(ctx.pendingTargetAngle, 0);
    assert_int_equal(ctx.pendingStep, 0);
    assert_int_equal(ctx.commandPending, 0);
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_protocol_init),
    };
    return cmocka_run_group_tests(tests, NULL, NULL);
}
