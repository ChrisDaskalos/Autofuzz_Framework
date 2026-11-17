#include "test_common.h"

static void test_wrong_password(void **state)
{
    (void)state;
    ProtocolContext ctx; 
    reset_ctx(&ctx);
    Protocol_ProcessCommand(&ctx, "badpwd");   /* wrong */

    assert_false(ctx.authenticated);           /* must still be 0 */
    assert_int_equal(ctx.state, STATE_MENU);   /* unchanged state */
}

int main(void)
{
    const struct CMUnitTest tests[] = 
    { 
        cmocka_unit_test(test_wrong_password) 
    };
    return cmocka_run_group_tests(tests, NULL, NULL);
}
