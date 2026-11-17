/*
 * Fake stm32f1xx_hal.h for AutoFuzz (PC build).
 *
 * Use it in autofuzz.yaml with:
 *     fake_include_dirs: [builtin:stm32f1_hal]
 * This folder then comes first on the include path, so `#include "stm32f1xx_hal.h"`
 * finds this file instead of the real HAL.
 *
 * It holds only HAL types, constants and function declarations. There are no
 * register addresses (no TIM2, USART2, GPIOA ...): code that uses them does
 * not compile on the PC and must be left out of `sources` or skipped.
 * The HAL functions are only declared here; AutoFuzz generates stub bodies
 * for the ones your sources call (see <output_dir>/stubs/stubs.c).
 *
 * Add a type or a declaration here when your firmware needs one.
 */
#ifndef AUTOFUZZ_FAKE_STM32F1XX_HAL_H
#define AUTOFUZZ_FAKE_STM32F1XX_HAL_H

#include <stdint.h>
#include <stddef.h>

/* ---- Status and lock ------------------------------------------------- */
typedef enum
{
  HAL_OK       = 0x00U,
  HAL_ERROR    = 0x01U,
  HAL_BUSY     = 0x02U,
  HAL_TIMEOUT  = 0x03U
} HAL_StatusTypeDef;

typedef enum
{
  HAL_UNLOCKED = 0x00U,
  HAL_LOCKED   = 0x01U
} HAL_LockTypeDef;

/* ---- Handles ----------------------------------------------------------
 * Instance points to the peripheral registers on the board. On the PC it
 * stays NULL; the fake macros below never use it.                        */
typedef struct
{
  void              *Instance;
  HAL_LockTypeDef    Lock;
  uint32_t           Compare[4];     /* last value set per channel (fake) */
} TIM_HandleTypeDef;

typedef struct
{
  void              *Instance;
  HAL_LockTypeDef    Lock;
} UART_HandleTypeDef;

typedef struct
{
  void              *Instance;
  HAL_LockTypeDef    Lock;
} DMA_HandleTypeDef;

/* ---- Timer ------------------------------------------------------------ */
#define TIM_CHANNEL_1  0x00000000U
#define TIM_CHANNEL_2  0x00000004U
#define TIM_CHANNEL_3  0x00000008U
#define TIM_CHANNEL_4  0x0000000CU

/* Real HAL: writes the CCRx register. Fake: remembers the value. */
#define __HAL_TIM_SET_COMPARE(__HANDLE__, __CHANNEL__, __COMPARE__) \
  ((__HANDLE__)->Compare[((__CHANNEL__) >> 2U) & 3U] = (uint32_t)(__COMPARE__))

HAL_StatusTypeDef HAL_TIM_PWM_Start(TIM_HandleTypeDef *htim, uint32_t Channel);
HAL_StatusTypeDef HAL_TIM_PWM_Stop(TIM_HandleTypeDef *htim, uint32_t Channel);

/* ---- UART ------------------------------------------------------------- */
HAL_StatusTypeDef HAL_UART_Transmit(UART_HandleTypeDef *huart, const uint8_t *pData,
                                    uint16_t Size, uint32_t Timeout);
HAL_StatusTypeDef HAL_UART_Receive(UART_HandleTypeDef *huart, uint8_t *pData,
                                   uint16_t Size, uint32_t Timeout);
HAL_StatusTypeDef HAL_UART_Transmit_DMA(UART_HandleTypeDef *huart, const uint8_t *pData, uint16_t Size);
HAL_StatusTypeDef HAL_UART_Receive_DMA(UART_HandleTypeDef *huart, uint8_t *pData, uint16_t Size);

/* ---- System ----------------------------------------------------------- */
void     HAL_Delay(uint32_t Delay);
uint32_t HAL_GetTick(void);

#endif /* AUTOFUZZ_FAKE_STM32F1XX_HAL_H */
