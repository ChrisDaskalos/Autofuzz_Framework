#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>
#include <limits.h>
#include <stdint.h>
#include <string.h>

#include "test_common.h"

static unsigned char a0_vals[] = { 0, 1, 2, 254, 255 };
#define a0_vals_LEN (sizeof(a0_vals)/sizeof(a0_vals[0]))
static unsigned char a1_vals[] = { 0, 1, 2, 254, 255 };
#define a1_vals_LEN (sizeof(a1_vals)/sizeof(a1_vals[0]))
static unsigned char a2_vals[] = { 0, 1, 2, 254, 255 };
#define a2_vals_LEN (sizeof(a2_vals)/sizeof(a2_vals[0]))

static void test_Servo_Ramp_safe_edge_1(void **state) {
    (void)state;
    unsigned char a0 = (unsigned char)0;
    unsigned char a1 = (unsigned char)0;
    unsigned char a2 = (unsigned char)0;

    /* Call target function */
    Servo_Ramp_safe(a0, a1, a2);

    /* Test passes if no crash/assertion */
}

static void test_Servo_Ramp_safe_edge_2(void **state) {
    (void)state;
    unsigned char a0 = (unsigned char)255;
    unsigned char a1 = (unsigned char)255;
    unsigned char a2 = (unsigned char)255;

    /* Call target function */
    Servo_Ramp_safe(a0, a1, a2);

    /* Test passes if no crash/assertion */
}

static void test_Servo_Ramp_safe_edge_3(void **state) {
    (void)state;
    unsigned char a0 = (unsigned char)2;
    unsigned char a1 = (unsigned char)2;
    unsigned char a2 = (unsigned char)2;

    /* Call target function */
    Servo_Ramp_safe(a0, a1, a2);

    /* Test passes if no crash/assertion */
}

static void test_Servo_Ramp_safe_edge_4(void **state) {
    (void)state;
    unsigned char a0 = (unsigned char)0;
    unsigned char a1 = (unsigned char)255;
    unsigned char a2 = (unsigned char)255;

    /* Call target function */
    Servo_Ramp_safe(a0, a1, a2);

    /* Test passes if no crash/assertion */
}

static void test_Servo_Ramp_safe_edge_5(void **state) {
    (void)state;
    unsigned char a0 = (unsigned char)255;
    unsigned char a1 = (unsigned char)0;
    unsigned char a2 = (unsigned char)0;

    /* Call target function */
    Servo_Ramp_safe(a0, a1, a2);

    /* Test passes if no crash/assertion */
}

static void test_Servo_Ramp_safe_edge_6(void **state) {
    (void)state;
    unsigned char a0 = (unsigned char)1;
    unsigned char a1 = (unsigned char)1;
    unsigned char a2 = (unsigned char)1;

    /* Call target function */
    Servo_Ramp_safe(a0, a1, a2);

    /* Test passes if no crash/assertion */
}

static void test_Servo_Ramp_safe_edge_7(void **state) {
    (void)state;
    unsigned char a0 = (unsigned char)254;
    unsigned char a1 = (unsigned char)254;
    unsigned char a2 = (unsigned char)254;

    /* Call target function */
    Servo_Ramp_safe(a0, a1, a2);

    /* Test passes if no crash/assertion */
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_Servo_Ramp_safe_edge_1),
        cmocka_unit_test(test_Servo_Ramp_safe_edge_2),
        cmocka_unit_test(test_Servo_Ramp_safe_edge_3),
        cmocka_unit_test(test_Servo_Ramp_safe_edge_4),
        cmocka_unit_test(test_Servo_Ramp_safe_edge_5),
        cmocka_unit_test(test_Servo_Ramp_safe_edge_6),
        cmocka_unit_test(test_Servo_Ramp_safe_edge_7),
    };
    return cmocka_run_group_tests_name("deterministic_edge_Servo_Ramp_safe", tests, NULL, NULL);
}
