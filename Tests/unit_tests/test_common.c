// test_common.c
#include "test_common.h"

/* Provide exactly one definition of these globals. */
TIM_HandleTypeDef htim2;
UART_HandleTypeDef huart2;
DMA_HandleTypeDef hdma_usart2_rx;
DMA_HandleTypeDef hdma_usart2_tx;
uint8_t dmaBuffer[DMA_BUFFER_SIZE] = {0};
