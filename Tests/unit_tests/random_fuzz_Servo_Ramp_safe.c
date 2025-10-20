#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>

#include "test_common.h"

#define AFZ_FZ_MAX_LEN 4096

/* Random fuzzer for Servo_Ramp_safe */
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (!data || size < 12) return 0;

    unsigned char a0 = (unsigned char)(data[0]);
    unsigned char a1 = (unsigned char)(data[1]);
    unsigned char a2 = (unsigned char)(data[2]);

    /* Call target function with fuzzer-derived inputs */
    Servo_Ramp_safe(a0, a1, a2);
    return 0;
}
