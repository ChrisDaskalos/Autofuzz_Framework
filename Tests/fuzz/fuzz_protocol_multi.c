/**
 * @file protocol_multi.c
 * @brief Mock firmware implementation of the protocol state machine and servo control.
 *
 * @details
 * This source file provides:
 *   - Fuzz‐safe abort macros for production vs. fuzz builds.
 *   - Global STM32 HAL shim instances (TIM2, UART2) and DMA buffer.
 *   - Protocol_Init(): Initializes the ProtocolContext with default values.
 *   - Protocol_ProcessCommand(): Stateless command parser supporting:
 *       • Authentication handling.
 *       • Cancellation during servo motion.
 *       • Servo command parsing in STATE_WAIT_SERVO with:
 *         – Delimiter normalization.
 *         – Base‐auto‐detect integer parsing.
 *         – Field count and range validation.
 *         – Optional checksum verification.
 *         – Command queuing and transition to STATE_RUNNING.
 *       • Main menu commands: servo submenu, shutdown, status/help stubs,
 *         and unknown-option handling.
 *   - Display helper stubs: Protocol_DisplayMenu(), Protocol_DisplayHelp().
 *   - ComputeChecksumFromNumbers(): Simple integer checksum function.
 *   - Servo mocks:
 *       • Servo_SetAngle(): Clamped angle setting via TIM compare macro.
 *       • Servo_Ramp(): Stepwise angle ramping with fuzz guards and HAL_Delay.
 *
 * This file is intended for unit testing and fuzzing of the protocol,
 * not production deployment.
 */

#include "test_common.h"
#include <string.h>   /* strchr, strlen */
#include <stdlib.h>   /* strtol */


#ifdef FUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION
#  define FUZZ_ABORT(fmt, ...)      do { fprintf(stderr, fmt, ##__VA_ARGS__); return; } while (0)
#else
#  define FUZZ_ABORT(fmt, ...)      do { fprintf(stderr, fmt, ##__VA_ARGS__); abort(); } while (0)
#endif

/* ────────── Global STM32 peripheral shims ─────────────────────── */
TIM_HandleTypeDef htim2;
UART_HandleTypeDef huart2;
uint8_t dmaBuffer[DMA_BUFFER_SIZE] = {0};

/* =================================================================
   Protocol implementation (mock firmware)
   ================================================================= */
void Protocol_Init(ProtocolContext *ctx)
{
    ctx->authenticated        = 0;
    ctx->current_servo_angle  = SERVO_DEFAULT_ANGLE;
    ctx->state                = STATE_MENU;
    ctx->cancelRequested      = 0;
    ctx->pendingTargetAngle   = 0;
    ctx->pendingStep          = 0;
    ctx->commandPending       = 0;
    strcpy(ctx->diagnostic_info, "AWAITING PASSWORD");
}

void Protocol_ProcessCommand(ProtocolContext *ctx, char *command)
{
    /* Trim trailing newline (matches firmware behaviour) */
    char *nl = strchr(command, '\n');
    if (nl) *nl = '\0';
    if (command[0] == '\0') return;

    /* ------------- LOGIN ----------------------------------------- */
    if (!ctx->authenticated) {
        if (strcmp(command, PROTOCOL_PASSWORD) == 0) {
            ctx->authenticated = 1;
            ctx->state         = STATE_MENU;
            strcpy(ctx->diagnostic_info, "AUTHENTICATED.");
        } else {
            strcpy(ctx->diagnostic_info, "AUTHENTICATION FAILED.");
        }
        return;
    }

    /* ------------- CANCEL WHILE RUNNING -------------------------- */
    if (ctx->state == STATE_RUNNING) {
        if (strcmp(command, "B") == 0 || strcmp(command, "b") == 0)
            ctx->cancelRequested = 1;
        return;
    }

    /* ------------- SERVO COMMAND ENTRY STATE --------------------- */
    if (ctx->state == STATE_WAIT_SERVO) {
        /* 1. Normalise delimiters -> space */
        char tmp[64];
        size_t j = 0;
        for (size_t i = 0; command[i] && j < sizeof(tmp) - 1; ++i) {
            char c = command[i];
            if (c == ',' || c == ';' || c == '(' || c == ')' || c == '\t')
                c = ' ';
            tmp[j++] = c;
        }
        tmp[j] = '\0';

        /* 2. Parse up to three integers (auto-detect base) */
        char *endp = tmp;
        long angle_l = strtol(endp, &endp, 0);
        long step_l  = strtol(endp, &endp, 0);
        long sum_l   = strtol(endp, &endp, 0);

        int fields = 0;
        if (endp != tmp) fields++;                 /* angle present */
        if (*(endp - 1) != '\0') fields++;         /* step present  */
        if (*endp != '\0')   fields++;             /* checksum maybe*/

        if (fields < 2) {                          /* too few nums  */
            HAL_UART_Transmit(&huart2,
                              (uint8_t*)CHECKSUM_ERROR_MSG,
                              strlen(CHECKSUM_ERROR_MSG),
                              UART_TX_TIMEOUT);
            return;
        }

        /* 3. Range checks */
        if (angle_l < 0 || angle_l > SERVO_MAX_ANGLE ||
            step_l  <= 0 || step_l  > SERVO_MAX_STEP)
        {
            HAL_UART_Transmit(&huart2,
                              (uint8_t*)UNKNOWN_MENU_OPTION_MSG, /* reuse msg */
                              strlen(UNKNOWN_MENU_OPTION_MSG),
                              UART_TX_TIMEOUT);
            return;
        }

        uint8_t angle_u = (uint8_t)angle_l;
        uint8_t step_u  = (uint8_t)step_l;

        /* 4. Optional checksum */
        if (fields == 3 &&
            (uint8_t)sum_l != ComputeChecksumFromNumbers(angle_u, step_u))
        {
            HAL_UART_Transmit(&huart2,
                              (uint8_t*)CHECKSUM_ERROR_MSG,
                              strlen(CHECKSUM_ERROR_MSG),
                              UART_TX_TIMEOUT);
            return;
        }

        /* 5. Schedule the move */
        ctx->pendingTargetAngle = angle_u;
        ctx->pendingStep        = step_u;
        ctx->commandPending     = 1;
        ctx->state              = STATE_RUNNING;
        return;
    }

    /* ------------- MAIN MENU ------------------------------------- */
    if (ctx->state == STATE_MENU && strlen(command) == 1) {
        switch (command[0]) {
            case '1':   /* Servo submenu */
                ctx->state = STATE_WAIT_SERVO;
                HAL_UART_Transmit(&huart2,
                                  (uint8_t*)SERVO_CMD_PROMPT,
                                  strlen(SERVO_CMD_PROMPT),
                                  UART_TX_TIMEOUT);
                break;

            case '2':   /* Shutdown */
                Servo_SetAngle(SERVO_DEFAULT_ANGLE);
                HAL_UART_Transmit(&huart2,
                                  (uint8_t*)MOTOR_SHUTDOWN_MSG,
                                  strlen(MOTOR_SHUTDOWN_MSG),
                                  UART_TX_TIMEOUT);
                break;

            case '3':   /* Status (stub) */
            case '4':   /* Help   (stub) */
                break;

            default:    /* Unknown option */
                HAL_UART_Transmit(&huart2,
                                  (uint8_t*)UNKNOWN_MENU_OPTION_MSG,
                                  strlen(UNKNOWN_MENU_OPTION_MSG),
                                  UART_TX_TIMEOUT);
        }
    }
}

/* ────────── Display helpers (stubs) ───────────────────────────── */
void Protocol_DisplayMenu(void)
{
    HAL_UART_Transmit(&huart2,
                      (uint8_t*)MENU_PROMPT,
                      strlen(MENU_PROMPT),
                      UART_TX_TIMEOUT);
}

void Protocol_DisplayHelp(void)
{
    HAL_UART_Transmit(&huart2,
                      (uint8_t*)HELP_MESSAGE,
                      strlen(HELP_MESSAGE),
                      UART_TX_TIMEOUT);
}

/* ────────── Utility functions ─────────────────────────────────── */
uint8_t ComputeChecksumFromNumbers(int angle, int step)
{
    return (uint8_t)(angle + step);
}

/* =================================================================
   Servo mocks
   ================================================================= */
void Servo_SetAngle(uint8_t angle)
{
    if (angle > SERVO_MAX_ANGLE) angle = SERVO_MAX_ANGLE;
    uint16_t pulse =
        SERVO_MIN_PULSE + ((angle * SERVO_PULSE_RANGE) / SERVO_MAX_ANGLE);
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, pulse);
}

void Servo_Ramp(uint8_t *currentAngle, uint8_t targetAngle, uint8_t step)
{
    if (step == 0 || step > SERVO_MAX_STEP) {
#ifdef FUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION
        fprintf(stderr, "[FUZZ] bad step=%d (ignored)\n", step);
        return;                                 /* keep fuzzing */
#else
        abort();
#endif
    }

    uint8_t current = *currentAngle;
    while (current != targetAngle) {
        if (current < targetAngle)
            current = (current + step > targetAngle) ?
                      targetAngle : current + step;
        else
            current = (current - step < targetAngle) ?
                      targetAngle : current - step;

        HAL_Delay(SERVO_RAMP_DELAY_MS);   /* no-op while fuzzing */
    }
    *currentAngle = current;
}

