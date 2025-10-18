#ifdef UNIT_TEST
    /* build for fuzzing / unit-test: stub HAL + no fatal asserts */
    #include "test_common.h"
#else
    /* production firmware build */
    #include "servo.h"
    #include "main.h"
    #include "protocol_defs.h"   /* UART_TX_TIMEOUT */
    #include <stdio.h>
    #include <string.h>
#endif
#include <assert.h>              /* <-- needed for the runtime assert */

void Servo_SetAngle(uint8_t angle)
{
    if (angle > SERVO_MAX_ANGLE) angle = SERVO_MAX_ANGLE;

    uint16_t pulse =
        SERVO_MIN_PULSE + ((angle * SERVO_PULSE_RANGE) / SERVO_MAX_ANGLE);
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, pulse);

#ifndef UNIT_TEST           /* keep verbose UART prints out of the fuzzer */
    char dbg[80];
    sprintf(dbg, "\r\n[DEBUG] SETTING SERVO TO %d (PULSE: %d)\r\n",
            angle, pulse);
    HAL_UART_Transmit(&huart2, (uint8_t*)dbg, strlen(dbg), UART_TX_TIMEOUT);
#endif
}

void Servo_Init(void)
{
    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1);
    Servo_SetAngle(SERVO_DEFAULT_ANGLE);
}

void Servo_Ramp(uint8_t *currentAngle, uint8_t targetAngle, uint8_t step)
{
#ifndef UNIT_TEST
    /* production build: fail fast if step is invalid */
    assert(step != 0 && step <= SERVO_MAX_STEP);
#else
    /* fuzz / unit-test: just ignore bogus steps so the fuzzer can keep going */
    if (step == 0 || step > SERVO_MAX_STEP) return;
#endif

    uint8_t current = *currentAngle;

    while (current != targetAngle) {
        if (current < targetAngle) {
            uint8_t next = (current + step > targetAngle)
                         ? targetAngle : current + step;
            Servo_SetAngle(next);
            current = next;
        } else {
            uint8_t next = (current < step) ? targetAngle : current - step;
            if (next < targetAngle) next = targetAngle;
            Servo_SetAngle(next);
            current = next;
        }
        HAL_Delay(SERVO_RAMP_DELAY_MS);   /* no-op in the HAL stubs   */
    }
    *currentAngle = current;
}
