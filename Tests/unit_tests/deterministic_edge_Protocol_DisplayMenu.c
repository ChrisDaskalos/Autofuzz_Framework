#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>
#include <limits.h>
#include <stdint.h>
#include <string.h>

#include "test_common.h"

static void test_Protocol_DisplayMenu_edge_1(void **state) {
    (void)state;

    /* Call target function */
    Protocol_DisplayMenu();

    /* Test passes if no crash/assertion */
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_Protocol_DisplayMenu_edge_1),
    };
    return cmocka_run_group_tests_name("deterministic_edge_Protocol_DisplayMenu", tests, NULL, NULL);
}
