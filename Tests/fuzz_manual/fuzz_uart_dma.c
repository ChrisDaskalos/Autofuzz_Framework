/**
 * @file fuzz_uart_dma.c
 * @brief Self-contained UART-DMA fuzz harness for protocol and servo firmware.
 *
 * @details
 * This harness drives the firmware’s UART-DMA path under libFuzzer, exercising:
 *   1. The firmware's own DMA buffer size (DMA_BUFFER_SIZE from
 *      protocol_defs.h, 1024 bytes), the same as Core/Src/main.c.
 *   2. The real protocol and servo interfaces (Protocol_ProcessCommand,
 *      Servo_Ramp, Servo_SetAngle).
 *   3. Global protocol context and DMA/UART handle definitions matching
 *      production firmware.
 *   4. Minimal HAL stubs for UART transmit/receive, DMA stop, and delays.
 *   5. The unmodified ProcessUartData() function, which copies incoming
 *      DMA data into a line buffer (with a deliberate no-bounds-check bug),
 *      echoes it over UART, and processes it as a protocol command.
 *   6. The HAL_UART_IdleCallback() stub, which stops DMA on idle,
 *      computes the received length, invokes ProcessUartData or clears the
 *      buffer during running state, and restarts DMA.
 *   7. A reset helper (init_test_env) to reinitialize protocol context,
 *      servo angle, DMA buffer, and DMA counter between fuzz iterations.
 *   8. The libFuzzer entry points LLVMFuzzerInitialize and
 *      LLVMFuzzerTestOneInput, which extract a fake DMA “Remaining” counter
 *      from the input, feed the remainder as DMA payload, authenticate,
 *      enter the servo menu, and invoke the idle callback under fuzz control.
 *
 * Build flags: -DUNIT_TEST -DFUZZING -fsanitize=fuzzer,address,undefined
 */

#include <stdint.h>
#include <string.h>

// -----------------------------------------------------------------------------
// 1) DMA_BUFFER_SIZE comes from protocol_defs.h (1024), like in the firmware.
//    (This used to #define it to 64 before the includes, but protocol_defs.h
//    redefined it to 1024, so 64 was never used.)
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
// 2) Pull in the real firmware interfaces
// -----------------------------------------------------------------------------
#include "protocol.h"      // ProtocolContext, Protocol_Init, Protocol_ProcessCommand, PROTOCOL_PASSWORD, STATE_*
#include "servo.h"         // Servo_Ramp, Servo_SetAngle, SERVO_DEFAULT_ANGLE

// -----------------------------------------------------------------------------
// 3) Define the globals exactly as your firmware expects them
// -----------------------------------------------------------------------------
extern ProtocolContext protocol_ctx;   /* defined in Core/Src/protocol.c */
uint8_t            dmaBuffer[DMA_BUFFER_SIZE];

typedef struct { uint32_t Remaining; } DMA_HandleTypeDef;
DMA_HandleTypeDef  hdma_usart2_rx;

typedef struct { void *Instance; } UART_HandleTypeDef;
UART_HandleTypeDef huart2;

// -----------------------------------------------------------------------------
// 4) Minimal HAL stubs
// -----------------------------------------------------------------------------
typedef enum { HAL_OK = 0x00U, HAL_ERROR = 0x01U } HAL_StatusTypeDef;
void HAL_UART_Transmit(UART_HandleTypeDef *h, const uint8_t *p, uint16_t n, uint32_t t) { (void)h;(void)p;(void)n;(void)t; }
void HAL_UART_Receive_DMA(UART_HandleTypeDef *h, uint8_t *p, uint32_t l) { (void)h;(void)p;(void)l; }
void HAL_UART_DMAStop(UART_HandleTypeDef *h) { (void)h; }
void HAL_Delay(uint32_t ms)           { (void)ms; }

// -----------------------------------------------------------------------------
// 5) The real firmware’s ProcessUartData (unmodified)
// -----------------------------------------------------------------------------
static void ProcessUartData(uint32_t length) {
    char lineBuffer[DMA_BUFFER_SIZE+1] = {0};
    // BUG here: no bounds check on length!
    memcpy(lineBuffer, dmaBuffer, length);
    lineBuffer[length] = '\0';

    HAL_UART_Transmit(&huart2, (uint8_t*)"\r\nReceived: ", 12, 100);
    HAL_UART_Transmit(&huart2, (uint8_t*)lineBuffer,
                      (uint16_t)strlen(lineBuffer), 100);
    Protocol_ProcessCommand(&protocol_ctx, lineBuffer);
}

// -----------------------------------------------------------------------------
// 6) The real firmware’s HAL_UART_IdleCallback (unmodified)
// -----------------------------------------------------------------------------
void HAL_UART_IdleCallback(UART_HandleTypeDef *huart) {
    (void)huart;
    HAL_UART_DMAStop(&huart2);
    uint32_t remain = hdma_usart2_rx.Remaining;
    uint32_t len    = DMA_BUFFER_SIZE - remain;

    if (protocol_ctx.state == STATE_RUNNING) {
        memset(dmaBuffer, 0, DMA_BUFFER_SIZE);
    } else if (len > 0) {
        ProcessUartData(len);
    }

    HAL_UART_Receive_DMA(&huart2, dmaBuffer, DMA_BUFFER_SIZE);
}

// -----------------------------------------------------------------------------
// 7) Simple reset between iterations
// -----------------------------------------------------------------------------
static void init_test_env(void) {
    memset(&protocol_ctx, 0, sizeof(protocol_ctx));
    protocol_ctx.current_servo_angle = SERVO_DEFAULT_ANGLE;
    protocol_ctx.state               = STATE_MENU;
    memset(dmaBuffer, 0, DMA_BUFFER_SIZE);
    hdma_usart2_rx.Remaining = DMA_BUFFER_SIZE;
}

// -----------------------------------------------------------------------------
// 8) libFuzzer entry points
// -----------------------------------------------------------------------------
int LLVMFuzzerInitialize(int *argc, char ***argv) {
    (void)argc; (void)argv;
    return 0;
}

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    if (Size < sizeof(uint32_t)) return 0;

    // Extract a fake DMA counter (4 bytes)
    uint32_t fakeRemaining;
    memcpy(&fakeRemaining, Data, sizeof(fakeRemaining));
    /* On the STM32F103 the DMA counter (CNDTR) starts at the buffer size
     * given to HAL_UART_Receive_DMA (DMA_BUFFER_SIZE) and only counts down,
     * so the firmware can only read 0..DMA_BUFFER_SIZE. Larger values made
     * `DMA_BUFFER_SIZE - remain` wrap and memcpy overflow: a finding that
     * cannot happen on the real board (a false finding of this harness). */
    fakeRemaining %= (uint32_t)DMA_BUFFER_SIZE + 1u;

    // Copy payload into dmaBuffer
    size_t payload = Size - sizeof(fakeRemaining);
    if (payload > DMA_BUFFER_SIZE) payload = DMA_BUFFER_SIZE;
    memcpy(dmaBuffer, Data + sizeof(fakeRemaining), payload);

    // Reset & login/menu
    init_test_env();
    Protocol_Init(&protocol_ctx);
    Protocol_ProcessCommand(&protocol_ctx, PROTOCOL_PASSWORD);
    Protocol_ProcessCommand(&protocol_ctx, "1");

    // Inject corrupted counter and call the real idle handler
    hdma_usart2_rx.Remaining = fakeRemaining;
    HAL_UART_IdleCallback(&huart2);

    return 0;
}
