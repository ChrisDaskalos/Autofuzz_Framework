#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>

#include "test_common.h"

#define AFZ_FZ_MAX_LEN 4096

/* Random fuzzer for reset_ctx */
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (!data || size < 4) return 0;

    /* Setup protocol context */
    ProtocolContext ctx;
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;


    /* Call target function with fuzzer-derived inputs */
    reset_ctx(&ctx);
    return 0;
}
