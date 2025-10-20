#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>

#include "test_common.h"

#define AFZ_FZ_MAX_LEN 4096

/* Random fuzzer for HAL_Delay */
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (!data || size < 4) return 0;

    unsigned int a0 = (unsigned int)(data[0]);

    /* Call target function with fuzzer-derived inputs */
    HAL_Delay(a0);
    return 0;
}
