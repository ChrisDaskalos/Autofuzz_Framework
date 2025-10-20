/**
 * @file test_protocol_checksum.c
 * @brief Unit test for the checksum computation function.
 *
 * @details
 * This file contains a CMocka test for the ComputeChecksumFromNumbers function
 * used in the protocol. It ensures that the checksum logic correctly sums two
 * uint8_t values and returns the expected result.
 *
 * Test included:
 *   - test_compute_checksum: verifies ComputeChecksumFromNumbers(90, 5) == 95
 *     and ComputeChecksumFromNumbers(100, 20) == 120.
 *
 * Registered and run via cmocka_run_group_tests in main().
 */
#include "test_common.h"

static void test_compute_checksum(void **state) {
    (void) state;
    uint8_t checksum = ComputeChecksumFromNumbers(90, 5);
    assert_int_equal(checksum, 95);
    checksum = ComputeChecksumFromNumbers(100, 20);
    assert_int_equal(checksum, 120);
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_compute_checksum),
    };
    return cmocka_run_group_tests(tests, NULL, NULL);
}
