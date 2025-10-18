#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>
#include <limits.h>
#include <stdint.h>
#include <string.h>

#include "test_common.h"

static unsigned char a0_vals[] = { 0, -1, 1 };
#define a0_vals_LEN (sizeof(a0_vals)/sizeof(a0_vals[0]))

static void test_Servo_SetAngle_edge_1(void **state) {
    (void)state;
    unsigned char a0 = (unsigned char)0;
    a0 = a0_vals[0];

    /* Call target function */
    Servo_SetAngle(a0);

    /* Test passes if no crash/assertion */
}

static void test_Servo_SetAngle_edge_2(void **state) {
    (void)state;
    unsigned char a0 = (unsigned char)0;
    a0 = a0_vals[1];

    /* Call target function */
    Servo_SetAngle(a0);

    /* Test passes if no crash/assertion */
}

static void test_Servo_SetAngle_edge_3(void **state) {
    (void)state;
    unsigned char a0 = (unsigned char)0;
    a0 = a0_vals[2];

    /* Call target function */
    Servo_SetAngle(a0);

    /* Test passes if no crash/assertion */
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_Servo_SetAngle_edge_1),
        cmocka_unit_test(test_Servo_SetAngle_edge_2),
        cmocka_unit_test(test_Servo_SetAngle_edge_3),
    };
    return cmocka_run_group_tests_name("deterministic_edge_Servo_SetAngle", tests, NULL, NULL);
}
