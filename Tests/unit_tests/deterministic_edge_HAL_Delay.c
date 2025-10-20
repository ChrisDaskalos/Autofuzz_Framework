#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>
#include <limits.h>
#include <stdint.h>
#include <string.h>

#include "test_common.h"

static unsigned int a0_vals[] = { INT_MIN, 0, 1, 2, 32768, 2147483648, 32767, 4294967294, 2147483647, 65535 };
#define a0_vals_LEN (sizeof(a0_vals)/sizeof(a0_vals[0]))

static void test_HAL_Delay_edge_1(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)INT_MIN;

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_2(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)0;

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_3(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)1;

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_4(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)2;

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_5(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)32768;

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_6(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)2147483648;

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_7(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)32767;

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_8(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)4294967294;

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_9(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)2147483647;

    /* Call target function */
    HAL_Delay(a0);

    /* Test passes if no crash/assertion */
}

static void test_HAL_Delay_edge_10(void **state) {
    (void)state;
    unsigned int a0 = (unsigned int)65535;

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
    };
    return cmocka_run_group_tests_name("deterministic_edge_HAL_Delay", tests, NULL, NULL);
}
