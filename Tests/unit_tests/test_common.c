/**
 * @file servo_ramp.c
 * @brief Implements servo angle ramping with fuzzing guards and global HAL shims.
 *
 * @details
 * This source file defines:
 *   - Global STM32 peripheral shim instances for TIM2 and UART2.
 *   - A DMA buffer used for UART transmissions in tests.
 *   - The Servo_Ramp() function, which safely steps a servo from its current
 *     angle to a target angle in increments of a specified step. Parameter
 *     checks abort on zero or overly large steps (fuzzing guards), debug
 *     messages are emitted via HAL_UART_Transmit, and each step is delayed
 *     by SERVO_RAMP_DELAY_MS.
 */

#include "test_common.h"

/* Global STM32 peripheral shims */
TIM_HandleTypeDef htim2;
UART_HandleTypeDef huart2;
//DMA_HandleTypeDef hdma_usart2_rx;
//DMA_HandleTypeDef hdma_usart2_tx;
uint8_t dmaBuffer[DMA_BUFFER_SIZE] = {0};

/* Servo_Ramp implementation with fuzzing guards */
void Servo_Ramp(uint8_t *currentAngle, uint8_t targetAngle, uint8_t step) {
    // Crash on invalid steps (critical for fuzzing)
    if (step == 0) {
        fprintf(stderr, "[FUZZ] ERROR: Step=0 in Servo_Ramp\n");
        abort();
    }
    if (step > SERVO_MAX_STEP) {
        fprintf(stderr, "[FUZZ] ERROR: Step=%d exceeds SERVO_MAX_STEP (%d)\n", 
                step, SERVO_MAX_STEP);
        abort();
    }

    uint8_t current = *currentAngle;
    
    // Simulate servo movement
    char dbg[80];
    snprintf(dbg, sizeof(dbg), "[DEBUG] Ramping from %d to %d (step=%d)\n", 
            current, targetAngle, step);
    HAL_UART_Transmit(&huart2, (uint8_t*)dbg, strlen(dbg), UART_TX_TIMEOUT);

    while (current != targetAngle) {
        if (current < targetAngle) {
            current = (current + step > targetAngle) ? targetAngle : current + step;
        } else {
            current = (current - step < targetAngle) ? targetAngle : current - step;
        }
        HAL_Delay(SERVO_RAMP_DELAY_MS);
    }
    
    *currentAngle = current;
}