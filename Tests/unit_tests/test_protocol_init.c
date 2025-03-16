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
