#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "test_common.h"

#define AFZ_FZ_MAX_LEN 4096

/* Random fuzzer for Protocol_ProcessCommand */
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (!data || size == 0) return 0;
    size_t n = size < (AFZ_FZ_MAX_LEN-1) ? size : (AFZ_FZ_MAX_LEN-1);
    char buf[AFZ_FZ_MAX_LEN];
    memcpy(buf, data, n);
    buf[n] = '\0';
    ProtocolContext ctx;
    reset_ctx(&ctx);
    ctx.authenticated = 1;
    ctx.state = STATE_WAIT_SERVO;
    Protocol_ProcessCommand(&ctx, buf);
    return 0;
}
