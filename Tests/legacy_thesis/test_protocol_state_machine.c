/**
 * @file test_protocol_state_machine.c
 * @brief Unit tests for state machine cancellation behavior in the protocol.
 *
 * @details
 * This file contains CMocka-based tests to verify how the protocol's state
 * machine handles cancellation requests. It checks:
 *   - Cancellation commands ('B' or 'b') when in STATE_RUNNING.
 *   - Ignoring cancellation when not in STATE_RUNNING.
 *   - Handling of whitespace around the cancel command.
 *   - Rejection of invalid cancel inputs with extra characters.
 * Tests assert that `cancelRequested` and `state` are correctly updated.
 */

#include "test_common.h"

/* 
 * Test 1: Cancellation when state is RUNNING with uppercase "B".
 * Expect cancelRequested to be set.
 */
static void test_state_machine_cancellation_when_running(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    /* Simulate a running command */
    ctx.state = STATE_RUNNING;
    ctx.cancelRequested = 0;

    char cancelCmd[] = "B";
    Protocol_ProcessCommand(&ctx, cancelCmd);

    assert_int_equal(ctx.cancelRequested, 1);
}

/* 
 * Test 2: Cancellation using lowercase "b".
 * Expect cancelRequested to be set.
 */
static void test_state_machine_cancellation_lowercase(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    ctx.state = STATE_RUNNING;
    ctx.cancelRequested = 0;

    char cancelCmd[] = "b";
    Protocol_ProcessCommand(&ctx, cancelCmd);

    assert_int_equal(ctx.cancelRequested, 1);
}

/*
 * Test 3: Cancellation command sent when state is not RUNNING.
 * Expect cancellation to be ignored.
 */
static void test_state_machine_ignore_cancellation_when_not_running(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    ctx.state = STATE_MENU;  // Not running
    ctx.cancelRequested = 0;

    char cancelCmd[] = "B";
    Protocol_ProcessCommand(&ctx, cancelCmd);

    assert_int_equal(ctx.cancelRequested, 0);
    assert_int_equal(ctx.state, STATE_MENU);
}

/*
 * Test 4: Cancellation command with extra whitespace.
 * 
 * If you extend the embedded code to trim leading/trailing whitespace,
 * then "   B   " should be accepted and set cancelRequested.
 *
 * If not, this test may need to expect no cancellation.
 */
static void test_state_machine_cancellation_with_whitespace(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    ctx.state = STATE_RUNNING;
    ctx.cancelRequested = 0;

    char cancelCmd[] = "   B   ";
    Protocol_ProcessCommand(&ctx, cancelCmd);

    /* Adjust the expectation based on your trimming implementation.
       Here we expect the input to be trimmed so that cancellation occurs. */
    assert_int_equal(ctx.cancelRequested, 1);
}

/*
 * Test 5: Cancellation command with extra invalid characters.
 * For example, "BEE" should be rejected as a cancellation command.
 */
static void test_state_machine_cancellation_invalid_format(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    ctx.state = STATE_RUNNING;
    ctx.cancelRequested = 0;

    char cancelCmd[] = "BEE";
    Protocol_ProcessCommand(&ctx, cancelCmd);

    /* Expect no cancellation since the command is not a single letter */
    assert_int_equal(ctx.cancelRequested, 0);
    /* The state remains unchanged (still RUNNING) */
    assert_int_equal(ctx.state, STATE_RUNNING);
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_state_machine_cancellation_when_running),
        cmocka_unit_test(test_state_machine_cancellation_lowercase),
        cmocka_unit_test(test_state_machine_ignore_cancellation_when_not_running),
        cmocka_unit_test(test_state_machine_cancellation_with_whitespace),
        cmocka_unit_test(test_state_machine_cancellation_invalid_format)
    };
    return cmocka_run_group_tests(tests, NULL, NULL);
}
