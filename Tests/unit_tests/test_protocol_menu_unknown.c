#include "test_common.h"

static void test_unknown_menu_key(void **state)
{
    (void)state;
    ProtocolContext ctx;  

    reset_ctx(&ctx);
    
    ctx.authenticated = 1;               /* already logged in */
    Protocol_ProcessCommand(&ctx, "x");  /* unknown key        */

    /* should stay in main menu and not crash                        */
    assert_int_equal(ctx.state, STATE_MENU);
    assert_false(ctx.commandPending);    /* nothing armed       */
}

int main(void)
{
    const struct CMUnitTest tests[] = 
    { 
        cmocka_unit_test(test_unknown_menu_key) 
    };
    return cmocka_run_group_tests(tests, NULL, NULL);
}
