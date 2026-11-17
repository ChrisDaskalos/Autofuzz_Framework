/**
 * @file test_protocol_servo_commands.c
 * @brief Unit tests for servo command parsing and queuing in the protocol.
 *
 * @details
 * This file defines a suite of CMocka unit tests to verify the handling
 * of servo movement commands issued to the protocol. It covers:
 *   - Valid command formats and checksum verification.
 *   - Error handling for invalid checksum, format, non-numeric input,
 *     extra/missing fields, zero or negative step values.
 *   - Parentheses-wrapped commands, clamping to maximum servo angle,
 *     and trimming of whitespace.
 * Tests assert that `commandPending`, `pendingTargetAngle`, `pendingStep`,
 * and `state` are updated as expected.
 */

#include "test_common.h"

/* 
 * Test: Valid servo command.
 * "90,5,95" is valid because 90+5==95.
 */
static void test_valid_servo_command(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    /* Authenticate and enter servo command mode */
    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "1");

    /* Use modifiable buffer */
    char cmd[] = "90,5,95";
    Protocol_ProcessCommand(&ctx, cmd);

    /* Expect command queued correctly */
    assert_int_equal(ctx.commandPending, 1);
    assert_int_equal(ctx.pendingTargetAngle, 90);
    assert_int_equal(ctx.pendingStep, 5);
}

/* 
 * Test: Invalid servo command due to bad checksum.
 * "90,5,96" is invalid because 90+5 != 96.
 */
static void test_invalid_servo_command_checksum(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "1");

    char cmd[] = "90,5,96";
    Protocol_ProcessCommand(&ctx, cmd);

    /* Expect no command queued and state reset to MENU */
    assert_int_equal(ctx.commandPending, 0);
    assert_int_equal(ctx.state, STATE_MENU);
}

/* 
 * Test: Invalid servo command format - missing a field.
 * For example "90,5" missing the checksum.
 */
static void test_invalid_servo_command_format(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "1");

    char cmd[] = "90,5";  // Missing checksum field.
    Protocol_ProcessCommand(&ctx, cmd);

    assert_int_equal(ctx.commandPending, 0);
    assert_int_equal(ctx.state, STATE_MENU);
}

/*
 * Test: Servo command with extra enclosing parentheses.
 * For example, "(90,5,95)" should be processed correctly.
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

/*
 * Test: Servo command clamping.
 * For example, "180,5,185" should clamp the angle to SERVO_MAX_ANGLE.
 */
static void test_servo_command_clamping(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "1");

    char cmd[20];
    /* Assuming SERVO_MAX_ANGLE is defined (e.g. 165) */
    snprintf(cmd, sizeof(cmd), "180,5,%d", 180 + 5);
    Protocol_ProcessCommand(&ctx, cmd);

    assert_int_equal(ctx.commandPending, 1);
    assert_int_equal(ctx.pendingTargetAngle, SERVO_MAX_ANGLE);
}

/*
 * Test: Servo command with non-numeric input.
 * For example, "ninety,5,95" should fail since "ninety" is not a valid integer.
 */
static void test_servo_command_non_numeric(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "1");

    char cmd[] = "ninety,5,95"; // "ninety" cannot be converted to int.
    Protocol_ProcessCommand(&ctx, cmd);

    /* Expect error: no command queued and state resets to MENU */
    assert_int_equal(ctx.commandPending, 0);
    assert_int_equal(ctx.state, STATE_MENU);
}

/*
 * Test: Servo command with extra fields.
 * For example, "90,5,95,100" should be rejected due to extra data.
 */
static void test_servo_command_extra_fields(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);
    
    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "1");
    
    char cmd[] = "90,5,95,100"; // Extra field beyond angle, step, checksum.
    Protocol_ProcessCommand(&ctx, cmd);
    
    /* Expect error: no command queued and state resets to MENU */
    assert_int_equal(ctx.commandPending, 0);
    assert_int_equal(ctx.state, STATE_MENU);
}

/*
 * Test: Servo command with zero step value.
 * A step of zero should be considered invalid (to avoid infinite loops).
 * Depending on implementation, this could be rejected or handled specially.
 */
static void test_servo_command_zero_step(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);
    
    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "1");
    
    char cmd[] = "90,0,90"; // 90+0 = 90, but step=0 is problematic.
    Protocol_ProcessCommand(&ctx, cmd);
    
    /* Expect error: no command queued; state should return to MENU.
       (Assumption: a step of zero is rejected to prevent an infinite loop) */
    assert_int_equal(ctx.commandPending, 0);
    assert_int_equal(ctx.state, STATE_MENU);
}

/*
 * Test: Servo command with negative step value.
 * Negative step values should be rejected.
 */
static void test_servo_command_negative_step(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);
    
    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "1");
    
    char cmd[] = "90,-5,85"; // 90 + (-5) = 85; negative step should be rejected.
    Protocol_ProcessCommand(&ctx, cmd);
    
    assert_int_equal(ctx.commandPending, 0);
    assert_int_equal(ctx.state, STATE_MENU);
}

/*
 * Test: Input with extra whitespace/newlines should be trimmed correctly.
 */
static void test_servo_command_trimming(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "1");
    
    char cmd[] = "   90,5,95 \n"; // Extra spaces and newline.
    Protocol_ProcessCommand(&ctx, cmd);
    
    assert_int_equal(ctx.commandPending, 1);
    assert_int_equal(ctx.pendingTargetAngle, 90);
    assert_int_equal(ctx.pendingStep, 5);
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_valid_servo_command),
        cmocka_unit_test(test_invalid_servo_command_checksum),
        cmocka_unit_test(test_invalid_servo_command_format),
        cmocka_unit_test(test_servo_command_with_parentheses),
        cmocka_unit_test(test_servo_command_clamping),
        cmocka_unit_test(test_servo_command_non_numeric),
        cmocka_unit_test(test_servo_command_extra_fields),
        cmocka_unit_test(test_servo_command_zero_step),
        cmocka_unit_test(test_servo_command_negative_step),
        cmocka_unit_test(test_servo_command_trimming)
    };
    return cmocka_run_group_tests(tests, NULL, NULL);
}
