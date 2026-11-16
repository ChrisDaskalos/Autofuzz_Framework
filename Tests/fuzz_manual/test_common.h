/**
 * @file test_common.h
 * @brief Common test harness and HAL stubs for protocol and servo unit tests and fuzzing.
 *
 * @details
 * This header defines:
 *   - Standard C library includes and project-specific headers for protocol and servo.
 *   - Dummy STM32 HAL type shims (TIM_HandleTypeDef, UART_HandleTypeDef, DMA_HandleTypeDef, HAL_StatusTypeDef).
 *   - Function prototypes for protocol initialization, command processing, display helpers, checksum computation, and servo control.
 *   - Configurable HAL stub implementations:
 *       • STRICT_HAL_STUBS: strict safety checks for fuzzing (UART overflow, excessive delays, pulse clamping).
 *       • Default no-op stubs for unit testing.
 *   - External declarations of global hardware simulators (htim2, huart2, dmaBuffer).
 */

#ifndef TEST_COMMON_H
#define TEST_COMMON_H

/* ────────────── Standard C Headers ─────────────────────────────────── */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <protocol.h>        /* defines ProtocolContext          */
#include <protocol_defs.h>   /* WELCOME_MSG, CMD_QUEUED_MSG …    */
#include <servo_defs.h>      /* SERVO_MAX_ANGLE, _STEP, DELAY …  */
#include <servo.h>

#define TIM_CHANNEL_1  0   /* dummy channel id for stubs */

/* ────────────── STM32 HAL Type Shims ───────────────────────────────── */
typedef struct { void *Instance; } TIM_HandleTypeDef;
typedef struct { void *Instance; } UART_HandleTypeDef;
typedef enum { HAL_OK = 0x00U, HAL_ERROR } HAL_StatusTypeDef;
typedef struct { uint32_t Remaining; } DMA_HandleTypeDef;


/* ────────────── Function Prototypes ────────────────────────────────── */
void Protocol_Init(ProtocolContext *ctx);
void Protocol_ProcessCommand(ProtocolContext *ctx, char *command);
void Protocol_DisplayMenu(void);
void Protocol_DisplayHelp(void);
uint8_t ComputeChecksumFromNumbers(int angle, int step);
void Servo_SetAngle(uint8_t angle);
void Servo_Ramp(uint8_t *currentAngle, uint8_t targetAngle, uint8_t step);

/* ────────────── Hardware Abstraction Layer (HAL) Stubs ──────────────── */
#ifdef STRICT_HAL_STUBS
/* Strict stubs for fuzzing with safety checks */

static uint16_t last_pulse;  // Track servo pulses for validation

#define __HAL_TIM_SET_COMPARE(htim, ch, val) \
    do { \
        last_pulse = (uint16_t)(val); \
        if (val < SERVO_MIN_PULSE) val = SERVO_MIN_PULSE; \
        if (val > SERVO_MAX_PULSE) val = SERVO_MAX_PULSE; \
    } while (0)

static inline HAL_StatusTypeDef HAL_TIM_PWM_Start(TIM_HandleTypeDef *h, uint32_t ch) {
    (void)h; (void)ch;
    return HAL_OK;
}

static inline HAL_StatusTypeDef HAL_UART_Transmit(UART_HandleTypeDef *h, 
                                                uint8_t *p,
                                                uint16_t n,
                                                uint32_t t) {
    if (n > DMA_BUFFER_SIZE) {
        fprintf(stderr, "[FUZZ] UART buffer overflow (Size=%d)\n", n);
        abort();
    }
    return HAL_OK;
}

static inline void HAL_Delay(uint32_t ms) {
    if (ms > SERVO_RAMP_DELAY_MS * 100) {  // Prevent infinite delays
        fprintf(stderr, "[FUZZ] Excessive delay: %d ms\n", ms);
        abort();
    }
}

#else
/* No-op stubs for unit testing */

#define __HAL_TIM_SET_COMPARE(htim, ch, val) ((void)0)

static inline HAL_StatusTypeDef HAL_TIM_PWM_Start(TIM_HandleTypeDef *h, uint32_t ch) {
    (void)h; (void)ch;
    return HAL_OK;
}

static inline HAL_StatusTypeDef HAL_UART_Transmit(UART_HandleTypeDef *h,
                                                uint8_t *p,
                                                uint16_t n,
                                                uint32_t t) {
    (void)h; (void)p; (void)n; (void)t;
    return HAL_OK;
}

static inline void HAL_Delay(uint32_t ms) {
    (void)ms;
}

#endif /* STRICT_HAL_STUBS */

/* ────────────── Global Hardware Simulators ─────────────────────────── */
extern TIM_HandleTypeDef htim2;
extern UART_HandleTypeDef huart2;
extern uint8_t dmaBuffer[DMA_BUFFER_SIZE];

#endif /* TEST_COMMON_H */