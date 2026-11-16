#include "test_common.h"

static void test_cancel_during_ramp(void **state)
{
    (void)state;
    ProtocolContext ctx; reset_ctx(&ctx);

    ctx.state = STATE_RUNNING;                 /* pretend ramping  */
    Protocol_ProcessCommand(&ctx, "B");        /* cancel command   */

    assert_true(ctx.cancelRequested);
    assert_int_equal(ctx.state, STATE_RUNNING);/* state unchanged  */
}

int main(void)
{
    const struct CMUnitTest tests[] = 
    {
        cmocka_unit_test(test_cancel_during_ramp),
    };
    return cmocka_run_group_tests(tests, NULL, NULL);
}
