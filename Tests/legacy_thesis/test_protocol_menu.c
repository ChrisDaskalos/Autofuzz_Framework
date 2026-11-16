#include "test_common.h"

static void test_menu_option_servo_command(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);
    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "1");
    assert_int_equal(ctx.state, STATE_WAIT_SERVO);
}

static void test_menu_option_shutdown(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);
    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "2");
    // Shutdown resets servo to default angle.
    assert_int_equal(ctx.current_servo_angle, SERVO_DEFAULT_ANGLE);
    assert_int_equal(ctx.state, STATE_MENU);
}

static void test_menu_option_display_status(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);
    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "3");
    assert_int_equal(ctx.state, STATE_MENU);
}

static void test_menu_option_help(void **state) {
    (void) state;
    ProtocolContext ctx;
    Protocol_Init(&ctx);
    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&ctx, "4");
    assert_int_equal(ctx.state, STATE_MENU);
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_menu_option_servo_command),
        cmocka_unit_test(test_menu_option_shutdown),
        cmocka_unit_test(test_menu_option_display_status),
        cmocka_unit_test(test_menu_option_help),
    };
    return cmocka_run_group_tests(tests, NULL, NULL);
}
