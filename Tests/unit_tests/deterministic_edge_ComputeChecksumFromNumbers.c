#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>
#include <limits.h>
#include <stdint.h>
#include <string.h>

#include "test_common.h"

static int a0_vals[] = { -2147483648, -2147483647, -32768, 0, 1, 2, 32768, 32767, -32768, 2147483647, 32767, 2147483646, 65535, 32768, -2, 2, 1, -1, -2147483647, 0, -2147483648, 2147483646, -1, 65535, -2, 2147483647 };
#define a0_vals_LEN (sizeof(a0_vals)/sizeof(a0_vals[0]))
static int a1_vals[] = { -2147483648, -2147483647, -32768, 0, 1, 2, 32768, 32767, -32768, 2147483647, 32767, 2147483646, 65535, 32768, -2, 2, 1, -1, -2147483647, 0, -2147483648, 2147483646, -1, 65535, -2, 2147483647 };
#define a1_vals_LEN (sizeof(a1_vals)/sizeof(a1_vals[0]))

static void test_ComputeChecksumFromNumbers_edge_1(void **state) {
    (void)state;
    int a0 = (int)0;
    int a1 = (int)0;
    a0 = a0_vals[0];
    a1 = a1_vals[0];

    /* Call target function */
    ComputeChecksumFromNumbers(a0, a1);

    /* Test passes if no crash/assertion */
}

static void test_ComputeChecksumFromNumbers_edge_2(void **state) {
    (void)state;
    int a0 = (int)0;
    int a1 = (int)0;
    a0 = a0_vals[1];
    a1 = a1_vals[1];

    /* Call target function */
    ComputeChecksumFromNumbers(a0, a1);

    /* Test passes if no crash/assertion */
}

static void test_ComputeChecksumFromNumbers_edge_3(void **state) {
    (void)state;
    int a0 = (int)0;
    int a1 = (int)0;
    a0 = a0_vals[2];
    a1 = a1_vals[2];

    /* Call target function */
    ComputeChecksumFromNumbers(a0, a1);

    /* Test passes if no crash/assertion */
}

static void test_ComputeChecksumFromNumbers_edge_4(void **state) {
    (void)state;
    int a0 = (int)0;
    int a1 = (int)0;
    a0 = a0_vals[3];
    a1 = a1_vals[3];

    /* Call target function */
    ComputeChecksumFromNumbers(a0, a1);

    /* Test passes if no crash/assertion */
}

static void test_ComputeChecksumFromNumbers_edge_5(void **state) {
    (void)state;
    int a0 = (int)0;
    int a1 = (int)0;
    a0 = a0_vals[4];
    a1 = a1_vals[4];

    /* Call target function */
    ComputeChecksumFromNumbers(a0, a1);

    /* Test passes if no crash/assertion */
}

static void test_ComputeChecksumFromNumbers_edge_6(void **state) {
    (void)state;
    int a0 = (int)0;
    int a1 = (int)0;
    a0 = a0_vals[5];
    a1 = a1_vals[5];

    /* Call target function */
    ComputeChecksumFromNumbers(a0, a1);

    /* Test passes if no crash/assertion */
}

static void test_ComputeChecksumFromNumbers_edge_7(void **state) {
    (void)state;
    int a0 = (int)0;
    int a1 = (int)0;
    a0 = a0_vals[6];
    a1 = a1_vals[6];

    /* Call target function */
    ComputeChecksumFromNumbers(a0, a1);

    /* Test passes if no crash/assertion */
}

static void test_ComputeChecksumFromNumbers_edge_8(void **state) {
    (void)state;
    int a0 = (int)0;
    int a1 = (int)0;
    a0 = a0_vals[7];
    a1 = a1_vals[7];

    /* Call target function */
    ComputeChecksumFromNumbers(a0, a1);

    /* Test passes if no crash/assertion */
}

static void test_ComputeChecksumFromNumbers_edge_9(void **state) {
    (void)state;
    int a0 = (int)0;
    int a1 = (int)0;
    a0 = a0_vals[8];
    a1 = a1_vals[8];

    /* Call target function */
    ComputeChecksumFromNumbers(a0, a1);

    /* Test passes if no crash/assertion */
}

static void test_ComputeChecksumFromNumbers_edge_10(void **state) {
    (void)state;
    int a0 = (int)0;
    int a1 = (int)0;
    a0 = a0_vals[9];
    a1 = a1_vals[9];

    /* Call target function */
    ComputeChecksumFromNumbers(a0, a1);

    /* Test passes if no crash/assertion */
}

static void test_ComputeChecksumFromNumbers_edge_11(void **state) {
    (void)state;
    int a0 = (int)0;
    int a1 = (int)0;
    a0 = a0_vals[10];
    a1 = a1_vals[10];

    /* Call target function */
    ComputeChecksumFromNumbers(a0, a1);

    /* Test passes if no crash/assertion */
}

static void test_ComputeChecksumFromNumbers_edge_12(void **state) {
    (void)state;
    int a0 = (int)0;
    int a1 = (int)0;
    a0 = a0_vals[11];
    a1 = a1_vals[11];

    /* Call target function */
    ComputeChecksumFromNumbers(a0, a1);

    /* Test passes if no crash/assertion */
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_ComputeChecksumFromNumbers_edge_1),
        cmocka_unit_test(test_ComputeChecksumFromNumbers_edge_2),
        cmocka_unit_test(test_ComputeChecksumFromNumbers_edge_3),
        cmocka_unit_test(test_ComputeChecksumFromNumbers_edge_4),
        cmocka_unit_test(test_ComputeChecksumFromNumbers_edge_5),
        cmocka_unit_test(test_ComputeChecksumFromNumbers_edge_6),
        cmocka_unit_test(test_ComputeChecksumFromNumbers_edge_7),
        cmocka_unit_test(test_ComputeChecksumFromNumbers_edge_8),
        cmocka_unit_test(test_ComputeChecksumFromNumbers_edge_9),
        cmocka_unit_test(test_ComputeChecksumFromNumbers_edge_10),
        cmocka_unit_test(test_ComputeChecksumFromNumbers_edge_11),
        cmocka_unit_test(test_ComputeChecksumFromNumbers_edge_12),
    };
    return cmocka_run_group_tests_name("deterministic_edge_ComputeChecksumFromNumbers", tests, NULL, NULL);
}
