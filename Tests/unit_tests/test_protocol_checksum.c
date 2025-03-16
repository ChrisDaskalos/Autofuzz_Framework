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
