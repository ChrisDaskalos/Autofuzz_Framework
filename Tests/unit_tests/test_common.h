#ifndef TEST_COMMON_H
#define TEST_COMMON_H

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <stdarg.h>
#include <setjmp.h>
#include <inttypes.h>
#include <cmocka.h>
#include <string.h>

// Minimal STM32/HAL stubs
typedef struct { void* Instance; } TIM_HandleTypeDef;
typedef struct { void* Instance; } UART_HandleTypeDef;
typedef struct { void* Instance; } DMA_HandleTypeDef;

typedef enum {
    HAL_OK = 0x00U,
    HAL_ERROR
} HAL_StatusTypeDef;

#define DMA_BUFFER_SIZE      64
#define TIM_CHANNEL_1        0
#define UART_TX_TIMEOUT      100
#define __HAL_TIM_SET_COMPARE(htim, channel, value)  do {} while(0)

static inline HAL_StatusTypeDef HAL_TIM_PWM_Start(TIM_HandleTypeDef *htim, uint32_t Channel) {
    (void)htim; (void)Channel;
    return HAL_OK;
}

static inline HAL_StatusTypeDef HAL_UART_Transmit(UART_HandleTypeDef *huart,
                                                  uint8_t *pData,
                                                  uint16_t Size,
                                                  uint32_t Timeout) {
    (void)huart; (void)pData; (void)Size; (void)Timeout;
    return HAL_OK;
}

static inline void HAL_Delay(uint32_t ms) {
    (void)ms;
}

// Fake the global variables your code references
/* Declare these global variables as 'extern'. */
extern TIM_HandleTypeDef htim2;
extern UART_HandleTypeDef huart2;
extern DMA_HandleTypeDef hdma_usart2_rx;
extern DMA_HandleTypeDef hdma_usart2_tx;
extern uint8_t dmaBuffer[DMA_BUFFER_SIZE];

// Finally include protocol/servo headers (now skipping main.h under UNIT_TEST)
#include "servo.h"
#include "protocol.h"
#include "protocol_defs.h"
#include "servo_defs.h"

#endif // TEST_COMMON_H
