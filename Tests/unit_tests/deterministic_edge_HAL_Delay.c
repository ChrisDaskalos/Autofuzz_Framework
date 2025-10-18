#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>
#include <limits.h>
#include <stdint.h>
#include <string.h>

#include "test_common.h"

static unsigned int a0_vals[] = { 0, 1, 2, 32768, 2147483648, 32767, 65535, 32767, 4294967295, 2, 4294967294, 65535, 2147483648, 0, 2147483647, 32768, 4294967295, 1, 4294967294, 2147483647 };
#define a0_vals_LEN (sizeof(a0_vals)/sizeof(a0_vals[0]))

static void test_HAL_Delay_edge_1(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)0;
    a0 = a0_vals[0];

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_2(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)0;
    a0 = a0_vals[1];

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_3(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)0;
    a0 = a0_vals[2];

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_4(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)0;
    a0 = a0_vals[3];

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_5(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)0;
    a0 = a0_vals[4];

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_6(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)0;
    a0 = a0_vals[5];

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_7(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)0;
    a0 = a0_vals[6];

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_8(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)0;
    a0 = a0_vals[7];

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_9(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)0;
    a0 = a0_vals[8];

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_10(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)0;
    a0 = a0_vals[9];

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_11(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)0;
    a0 = a0_vals[10];

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_12(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)0;
    a0 = a0_vals[11];

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_HAL_Delay_edge_1),
        cmocka_unit_test(test_HAL_Delay_edge_2),
        cmocka_unit_test(test_HAL_Delay_edge_3),
        cmocka_unit_test(test_HAL_Delay_edge_4),
        cmocka_unit_test(test_HAL_Delay_edge_5),
        cmocka_unit_test(test_HAL_Delay_edge_6),
        cmocka_unit_test(test_HAL_Delay_edge_7),
        cmocka_unit_test(test_HAL_Delay_edge_8),
        cmocka_unit_test(test_HAL_Delay_edge_9),
        cmocka_unit_test(test_HAL_Delay_edge_10),
        cmocka_unit_test(test_HAL_Delay_edge_11),
        cmocka_unit_test(test_HAL_Delay_edge_12),
    };
    return cmocka_run_group_tests_name("deterministic_edge_HAL_Delay", tests, NULL, NULL);
}
