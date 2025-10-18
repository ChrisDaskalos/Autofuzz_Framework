#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>

#include "test_common.h"

#define AFZ_FZ_MAX_LEN 4096

/* Random fuzzer for ComputeChecksumFromNumbers */
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (!data || size < 8) return 0;

    int32_t a0;
    memcpy(&a0, data + 0, sizeof(int32_t));
    int32_t a1;
    memcpy(&a1, data + 4, sizeof(int32_t));

    /* Call target function with fuzzer-derived inputs */
    ComputeChecksumFromNumbers(a0, a1);
    return 0;
}
