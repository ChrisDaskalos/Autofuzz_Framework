#include "test_common.h"

/* Test that when the protocol state is RUNNING,
   sending a cancellation command "B" sets cancelRequested to 1.
*/
static void test_state_machine_cancellation_when_running(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    /* Simulate that a command is running */
    ctx.state = STATE_RUNNING;
    ctx.cancelRequested = 0;

    /* Pass a modifiable cancellation command */
    char cancelCmd[] = "B";
    Protocol_ProcessCommand(&ctx, cancelCmd);

    assert_int_equal(ctx.cancelRequested, 1);
}

/* Test that if the protocol state is not RUNNING,
   sending "B" does not affect the cancellation flag.
*/
static void test_state_machine_ignore_cancellation_when_not_running(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    /* Ensure state is MENU (not RUNNING) */
    ctx.state = STATE_MENU;
    ctx.cancelRequested = 0;

    char cancelCmd[] = "B";
    Protocol_ProcessCommand(&ctx, cancelCmd);

    /* Expect that cancellation is ignored */
    assert_int_equal(ctx.cancelRequested, 0);
    assert_int_equal(ctx.state, STATE_MENU);
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_state_machine_cancellation_when_running),
        cmocka_unit_test(test_state_machine_ignore_cancellation_when_not_running),
    };
    return cmocka_run_group_tests(tests, NULL, NULL);
}
