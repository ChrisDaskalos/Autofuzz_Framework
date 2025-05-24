/**
 * @file test_common.h
 * @brief Common test harness definitions and HAL stubs for unit testing and fuzzing.
 *
 * @details
 * This header provides:
 *   - Standard library includes and type definitions needed by tests.
 *   - Dummy STM32 HAL handle structs and status codes.
 *   - Project constants: DMA_BUFFER_SIZE and UART_TX_TIMEOUT.
 *   - Inclusion of servo_defs.h for SERVO_MIN_PULSE, SERVO_MAX_PULSE, etc.
 *   - Strict or no-op HAL stub implementations for TIM PWM start,
 *     compare setting, and UART transmit (used to detect errors during fuzzing).
 *   - External declarations of global handles htim2 and huart2.
 */

#ifndef TEST_COMMON_H
#define TEST_COMMON_H

/* ────────────── Standard Libraries ─────────────────────────────────── */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>

/* ────────────── STM32 Hardware Abstraction Layer (HAL) Shims ───────── */
typedef struct { void *Instance; } TIM_HandleTypeDef;
typedef struct { void *Instance; } UART_HandleTypeDef;
typedef enum { HAL_OK = 0x00U, HAL_ERROR } HAL_StatusTypeDef;

/* ────────────── Project Constants ──────────────────────────────────── */
#define DMA_BUFFER_SIZE  64
#define UART_TX_TIMEOUT  100
#include "servo_defs.h"  // SERVO_MIN_PULSE, SERVO_MAX_PULSE

/* ────────────── Strict HAL Stubs for Fuzzing ───────────────────────── */
#ifdef STRICT_HAL_STUBS

static uint16_t last_pulse;

static inline HAL_StatusTypeDef HAL_TIM_PWM_Start(TIM_HandleTypeDef *h, uint32_t ch) {
    (void)h; (void)ch; 
    return HAL_OK;
}

#define __HAL_TIM_SET_COMPARE(htim, ch, val) \
    do { \
        last_pulse = (uint16_t)(val); \
        if (val < SERVO_MIN_PULSE) val = SERVO_MIN_PULSE; \
        if (val > SERVO_MAX_PULSE) val = SERVO_MAX_PULSE; \
    } while (0)

static inline HAL_StatusTypeDef HAL_UART_Transmit(UART_HandleTypeDef *h, uint8_t *p, uint16_t n, uint32_t t) {
    if (n > DMA_BUFFER_SIZE) { 
        fprintf(stderr, "[FUZZ] ERROR: UART buffer overflow (Size=%d)\n", n);
        abort(); 
    }
    return HAL_OK;
}

#else  // No-op stubs for unit tests

#define __HAL_TIM_SET_COMPARE(htim, ch, val) ((void)0)

static inline HAL_StatusTypeDef HAL_TIM_PWM_Start(TIM_HandleTypeDef *h, uint32_t ch) { 
    (void)h; (void)ch; 
    return HAL_OK; 
}

static inline HAL_StatusTypeDef HAL_UART_Transmit(UART_HandleTypeDef *h, uint8_t *p, uint16_t n, uint32_t t) { 
    (void)h; (void)p; (void)n; (void)t; 
    return HAL_OK; 
}

#endif // STRICT_HAL_STUBS

/* ────────────── Global Variables ───────────────────────────────────── */
extern TIM_HandleTypeDef htim2;
extern UART_HandleTypeDef huart2;

#endif // TEST_COMMON_H