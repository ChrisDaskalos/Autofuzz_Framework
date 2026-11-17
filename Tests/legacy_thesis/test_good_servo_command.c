#include "test_common.h"

static void test_good_servo_command(void **state)
{
    (void)state;
    ProtocolContext ctx; 
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;

    Protocol_ProcessCommand(&ctx, "30,2,32");

    assert_true(ctx.commandPending);
    assert_int_equal(ctx.pendingTargetAngle, 30);
    assert_int_equal(ctx.pendingStep,       2);
    assert_int_equal(ctx.state, STATE_WAIT_SERVO);
}

int main(void)
{
    const struct CMUnitTest tests[]= { cmocka_unit_test(test_good_servo_command) };
    return cmocka_run_group_tests(tests, NULL, NULL);
}
