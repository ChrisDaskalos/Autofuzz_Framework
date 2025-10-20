#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>

#include "test_common.h"

#define AFZ_FZ_MAX_LEN 4096

/* Random fuzzer for Servo_SetAngle */
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (!data || size < 4) return 0;

    unsigned char a0 = (unsigned char)(data[0]);

    /* Call target function with fuzzer-derived inputs */
    Servo_SetAngle(a0);
    return 0;
}
