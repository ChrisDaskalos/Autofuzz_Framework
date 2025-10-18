#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>

#include "test_common.h"

#define AFZ_FZ_MAX_LEN 4096

/* Random fuzzer for Servo_Init */
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (!data || size < 1) return 0;


    /* Call target function with fuzzer-derived inputs */
    Servo_Init();
    return 0;
}
