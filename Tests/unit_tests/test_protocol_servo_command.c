#include "test_common.h"

/* Test a valid servo command.
   "90,5,95" is valid because 90 + 5 == 95.
*/
static void test_valid_servo_command(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    // Authenticate first.
    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    // Enter servo command mode.
    Protocol_ProcessCommand(&ctx, "1");

    /* Use a modifiable buffer instead of a string literal */
    char cmd[] = "90,5,95";
    Protocol_ProcessCommand(&ctx, cmd);

    /* Expect the command to be queued properly */
    assert_int_equal(ctx.commandPending, 1);
    assert_int_equal(ctx.pendingTargetAngle, 90);
    assert_int_equal(ctx.pendingStep, 5);
}

/* Test an invalid servo command due to a bad checksum.
   "90,5,96" is invalid because 90 + 5 != 96.
*/
static void test_invalid_servo_command_checksum(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "1");

    char cmd[] = "90,5,96";
    Protocol_ProcessCommand(&ctx, cmd);

    /* Expect no command is queued and state resets to MENU */
    assert_int_equal(ctx.commandPending, 0);
    assert_int_equal(ctx.state, STATE_MENU);
}

/* Test an invalid format (missing a field), e.g., "90,5" */
static void test_invalid_servo_command_format(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "1");

    char cmd[] = "90,5";  // Missing the checksum field.
    Protocol_ProcessCommand(&ctx, cmd);

    /* Expect error: no command queued and state resets to MENU */
    assert_int_equal(ctx.commandPending, 0);
    assert_int_equal(ctx.state, STATE_MENU);
}

/* Test a servo command with extra enclosing parentheses,
   e.g. "(90,5,95)" should be handled correctly.
*/
static void test_servo_command_with_parentheses(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "1");

    char cmd[] = "(90,5,95)";
    Protocol_ProcessCommand(&ctx, cmd);

    assert_int_equal(ctx.commandPending, 1);
    assert_int_equal(ctx.pendingTargetAngle, 90);
    assert_int_equal(ctx.pendingStep, 5);
}

/* Test that an out-of-range angle is clamped.
   For example, if a command "180,5,185" is sent and SERVO_MAX_ANGLE is defined (e.g. 165),
   then the angle should be clamped to SERVO_MAX_ANGLE.
*/
static void test_servo_command_clamping(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "1");

    char cmd[20];
    // "180,5,185" is sent but angle should be clamped to SERVO_MAX_ANGLE.
    snprintf(cmd, sizeof(cmd), "180,5,%d", 180 + 5);
    Protocol_ProcessCommand(&ctx, cmd);

    assert_int_equal(ctx.commandPending, 1);
    assert_int_equal(ctx.pendingTargetAngle, SERVO_MAX_ANGLE);
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_valid_servo_command),
        cmocka_unit_test(test_invalid_servo_command_checksum),
        cmocka_unit_test(test_invalid_servo_command_format),
        cmocka_unit_test(test_servo_command_with_parentheses),
        cmocka_unit_test(test_servo_command_clamping),
    };
    return cmocka_run_group_tests(tests, NULL, NULL);
}
