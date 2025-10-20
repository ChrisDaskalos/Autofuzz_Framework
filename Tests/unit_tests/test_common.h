/*  test_common.h  ─ host-side HAL + protocol/servo “facade” for unit & fuzz */

#ifndef TEST_COMMON_H
#define TEST_COMMON_H

/* ─── tool‑chain / CMocka ─────────────────────────────────────────────── */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <setjmp.h>     /* must precede <cmocka.h> */
#include <stdarg.h>
#include <cmocka.h>


/* ─── production constants we want the tests to use ───────────────────── */
#include "protocol_defs.h"   /* PROTOCOL_PASSWORD, PROTOCOL_DIAG_SIZE … */
#include "servo_defs.h"      /* SERVO_MAX_ANGLE, SERVO_DEFAULT_ANGLE … */
#include "protocol.h"        /* ProtocolState, ProtocolContext, API     */

/* ─── minimal STM32 HAL stand‑ins ─────────────────────────────────────── */
typedef struct { void *Instance; } TIM_HandleTypeDef;
typedef struct { void *Instance; } UART_HandleTypeDef;
typedef enum   { HAL_OK = 0, HAL_ERROR } HAL_StatusTypeDef;

#define __HAL_TIM_SET_COMPARE(htim,ch,val)   ((void)0)

static inline HAL_StatusTypeDef HAL_TIM_PWM_Start(TIM_HandleTypeDef *h, uint32_t c)
{ (void)h; (void)c; return HAL_OK; }

/* Declare UART transmit; real body is in test_common.c (with assert) */
static inline HAL_StatusTypeDef HAL_UART_Transmit(UART_HandleTypeDef *h, uint8_t *p, uint16_t n, uint32_t t)
{
    (void)h; (void)t;
    if (!p) return HAL_OK;
    /* Bounded length check to avoid over-reads under tests */
    size_t actual = strnlen((const char*)p, 4096);
    assert(n <= actual && "HAL_UART_Transmit length exceeds string size");
    return HAL_OK;
}


void HAL_Delay(uint32_t ms);  /* implemented in test_common.c */

/* ─── globals firmware expects ────────────────────────────────────────── */
extern TIM_HandleTypeDef htim2;
extern UART_HandleTypeDef huart2;

/* ─── public helpers exposed to unit‑tests & fuzzers ──────────────────── */
//static int  ascii_to_int(const char *s, int *out);
void reset_ctx(ProtocolContext *ctx);

/* Servo façade so host tests can link */
void Servo_SetAngle(uint8_t angle);
// void Servo_Ramp(uint8_t *cur, uint8_t tgt, uint8_t step);
void Servo_Init(void);
uint8_t Servo_Ramp_safe(uint8_t cur, uint8_t tgt, uint8_t step);

#endif /* TEST_COMMON_H */
