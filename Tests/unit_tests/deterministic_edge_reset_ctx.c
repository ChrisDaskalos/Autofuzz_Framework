#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>
#include <limits.h>
#include <stdint.h>
#include <string.h>

#include "test_common.h"


static void test_reset_ctx_edge_1(void **state) {
    (void)state;
    ProtocolContext ctx;

    /* Call target function */
    reset_ctx(&ctx);

    /* Test passes if no crash/assertion */
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_reset_ctx_edge_1),
    };
    return cmocka_run_group_tests_name("deterministic_edge_reset_ctx", tests, NULL, NULL);
}
