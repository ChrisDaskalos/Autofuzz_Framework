#ifdef UNIT_TEST
	#include "test_common.h"
#else
	#include "servo.h"
	#include "main.h"
	#include "protocol_defs.h"  // Add this to bring in UART_TX_TIMEOUT
	#include <stdio.h>
	#include <string.h>
#endif


void Servo_SetAngle(uint8_t angle)
{
    if (angle > SERVO_MAX_ANGLE)
        angle = SERVO_MAX_ANGLE;

    // Map angle to PWM pulse.
    uint16_t pulse = SERVO_MIN_PULSE + ((angle * SERVO_PULSE_RANGE) / SERVO_MAX_ANGLE);
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, pulse);

    char dbg[80];
    sprintf(dbg, "\r\n[DEBUG] SETTING SERVO TO %d (PULSE: %d)\r\n", angle, pulse);
    HAL_UART_Transmit(&huart2, (uint8_t*)dbg, strlen(dbg), UART_TX_TIMEOUT);

    char setMsg[60];
    sprintf(setMsg, "SERVO ANGLE SET TO: %d (PULSE: %d)\r\n", angle, pulse);
    HAL_UART_Transmit(&huart2, (uint8_t*)setMsg, strlen(setMsg), UART_TX_TIMEOUT);
}

void Servo_Init(void)
{
    // Start PWM output for the servo (assumes htim2 is configured and initialized)
    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1);

    // Set the servo to its default angle.
    Servo_SetAngle(SERVO_DEFAULT_ANGLE);
}



void Servo_Ramp(uint8_t *currentAngle, uint8_t targetAngle, uint8_t step)
{
    uint8_t current = *currentAngle;

    char dbg[80];
    sprintf(dbg, "\r\n[DEBUG] RAMP FROM %d TO %d STEP=%d\r\n", current, targetAngle, step);
    HAL_UART_Transmit(&huart2, (uint8_t*)dbg, strlen(dbg), UART_TX_TIMEOUT);

    if (current < targetAngle)
    {
        while (current < targetAngle)
        {
            uint8_t newAngle = (current + step > targetAngle) ? targetAngle : (current + step);
            Servo_SetAngle(newAngle);
            HAL_Delay(SERVO_RAMP_DELAY_MS);
            current = newAngle;
        }
    }
    else if (current > targetAngle)
    {
        while (current > targetAngle)
        {
            uint8_t newAngle = (current < step) ? targetAngle : current - step;
            if (newAngle < targetAngle)
                newAngle = targetAngle;
            Servo_SetAngle(newAngle);
            HAL_Delay(SERVO_RAMP_DELAY_MS);
            current = newAngle;
        }
    }
    *currentAngle = current;
}
