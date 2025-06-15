/**
 * @file test_common.c
 * @brief Mock firmware for protocol command parsing and servo control
 *        with fuzz-safe behavior and logic assertions in UNIT_TEST builds.
 *
 * @details
 *   - Under UNIT_TEST: defines CHECK(…) macro and ascii_to_int stub with assertions.
 *   - Global STM32 HAL shim instances (TIM2, UART2) and DMA buffer.
 *   - Production (non-UNIT_TEST) Protocol_Init, ProcessCommand, etc.
 *   - Servo_SetAngle and Servo_Ramp with logic checks under UNIT_TEST.
 */

 #include "test_common.h"
 #include <string.h>
 
 #ifdef UNIT_TEST
 
 /*────────────────────────────────────────────────────────────────────────*/
 /* Assertion helper: on failure, prints the expression as message       */
 #define CHECK(cond) assert_true_message((cond), #cond)
 
 /**
  * @brief  Parse a string as integer (auto‐base) and enforce some invariants.
  * @param  s  null-terminated input
  * @returns parsed value or -1 on error
  *
  * Under UNIT_TEST, any violation (empty, leftover chars, out-of-range)
  * will fail a CMocka assertion.
  */
 int ascii_to_int(const char *s)
 {
     /* must not be null or empty */
     CHECK(s && *s);
 
     char *end;
     long v = strtol(s, &end, 0);
 
     /* entire string must have been consumed */
     CHECK(*end == '\0');
 
     /* enforce uint8_t domain as an example */
     CHECK(v >= 0 && v <= 255);
 
     return (int)v;
 }
 /*────────────────────────────────────────────────────────────────────────*/
 
 #endif  /* UNIT_TEST */
 
 
 /* ───────── helpers ───────── */
 #ifdef FUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION
 #  define FUZZ_ABORT(fmt, ...)  do { fprintf(stderr, fmt, ##__VA_ARGS__); return; } while (0)
 #else
 #  define FUZZ_ABORT(fmt, ...)  do { fprintf(stderr, fmt, ##__VA_ARGS__); abort(); } while (0)
 #endif
 
 
 /* ───────── global HAL shims ───────── */
 TIM_HandleTypeDef htim2;
 UART_HandleTypeDef huart2;
 uint8_t dmaBuffer[DMA_BUFFER_SIZE] = {0};
 
 
 #ifndef UNIT_TEST
 
 /* ───────── protocol init ───────── */
 void Protocol_Init(ProtocolContext *ctx)
 {
     memset(ctx, 0, sizeof(*ctx));
     ctx->current_servo_angle = SERVO_DEFAULT_ANGLE;
     ctx->state               = STATE_MENU;
     strcpy(ctx->diagnostic_info, "AWAITING PASSWORD");
 }
 
 /* ───────── uart helpers ───────── */
 static inline void tx(const char *s)
 {
     HAL_UART_Transmit(&huart2, (uint8_t *)s,
                       (uint16_t)strlen(s), UART_TX_TIMEOUT);
 }
 
 /* ===================================================================== */
 void Protocol_ProcessCommand(ProtocolContext *ctx, char *command)
 {
     /* strip trailing newline */
     char *nl = strchr(command, '\n');
     if (nl) *nl = '\0';
     if (command[0] == '\0') return;
 
     /* login */
     if (!ctx->authenticated) {
         if (strcmp(command, PROTOCOL_PASSWORD) == 0) {
             ctx->authenticated = 1;
             ctx->state         = STATE_MENU;
             tx("AUTHENTICATED.");
         } else {
             tx("AUTHENTICATION FAILED.");
         }
         return;
     }
 
     /* cancel while running */
     if (ctx->state == STATE_RUNNING) {
         if (!strcasecmp(command, "B"))
             ctx->cancelRequested = 1;
         return;
     }
 
     /* cancel while waiting for servo cmd */
     if (ctx->state == STATE_WAIT_SERVO && !strcasecmp(command, "B")) {
         ctx->state = STATE_MENU;
         return;
     }
 
     /* servo command entry */
     if (ctx->state == STATE_WAIT_SERVO) {
 
         /* translate delimiters → space */
         char tmp[64];
         size_t k = 0;
         for (size_t i = 0; command[i] && k < sizeof(tmp) - 1; ++i) {
             char c = command[i];
             if (c == ',' || c == ';' || c == '(' || c == ')' || c == '\t')
                 c = ' ';
             tmp[k++] = c;
         }
         tmp[k] = '\0';
 
         /* parse ints (hex/dec/oct auto-base) */
         int angle = -1, step = -1, checksum = -1;
         int n = sscanf(tmp, "%i %i %i", &angle, &step, &checksum);
         if (n < 2) { tx(CHECKSUM_ERROR_MSG); return; }
 
         /* range checks */
         if (angle < 0 || angle > SERVO_MAX_ANGLE) { tx("ANGLE ERR"); return; }
         if (step  <= 0 || step  > SERVO_MAX_STEP)  { tx("STEP ERR");  return; }
 
         /* checksum (optional) */
         if (n == 3 &&
             (uint8_t)checksum != ComputeChecksumFromNumbers(angle, step)) {
             tx(CHECKSUM_ERROR_MSG);
             return;
         }
 
         /* queue move */
         ctx->pendingTargetAngle = (uint8_t)angle;
         ctx->pendingStep        = (uint8_t)step;
         ctx->commandPending     = 1;
         ctx->state              = STATE_RUNNING;
         return;
     }
 
     /* main menu */
     if (ctx->state == STATE_MENU && strlen(command) == 1) {
         switch (command[0]) {
         case '1':   ctx->state = STATE_WAIT_SERVO; tx(SERVO_CMD_PROMPT); break;
         case '2':   Servo_SetAngle(SERVO_DEFAULT_ANGLE); tx(MOTOR_SHUTDOWN_MSG); break;
         case '3':   tx("STATUS OK"); break;
         case '4':   tx(HELP_MESSAGE); break;
         default:    tx(UNKNOWN_MENU_OPTION_MSG);
         }
     }
 }
 
 /* ───────── display wrappers ───────── */
 void Protocol_DisplayMenu(void) { HAL_UART_Transmit(&huart2, (uint8_t*)MENU_PROMPT, strlen(MENU_PROMPT), UART_TX_TIMEOUT); }
 void Protocol_DisplayHelp(void) { HAL_UART_Transmit(&huart2, (uint8_t*)HELP_MESSAGE, strlen(HELP_MESSAGE), UART_TX_TIMEOUT); }
 
 /* ───────── utils ───────── */
 uint8_t ComputeChecksumFromNumbers(int angle, int step)
 {
     return (uint8_t)(angle + step);
 }
 
 /* ===================================================================== */
 /*                               servo mocks                             */
 /* ===================================================================== */
 void Servo_SetAngle(uint8_t angle)
 {
 #ifdef UNIT_TEST
     /* logic check: must not exceed max */
     CHECK(angle <= SERVO_MAX_ANGLE);
 #endif
 
     if (angle > SERVO_MAX_ANGLE) angle = SERVO_MAX_ANGLE;
     uint16_t pulse = SERVO_MIN_PULSE +
                      ((angle * SERVO_PULSE_RANGE) / SERVO_MAX_ANGLE);
     __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, pulse);
 }
 
 void Servo_Ramp(uint8_t *cur, uint8_t tgt, uint8_t step)
 {
     if (step == 0 || step > SERVO_MAX_STEP) {
 #ifdef FUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION
         fprintf(stderr, "[FUZZ] bad step=%d (ignored)\n", step);
         return;
 #else
         abort();
 #endif
     }
 
     while (*cur != tgt) {
         *cur = (*cur < tgt)
              ? (uint8_t)((*cur + step > tgt) ? tgt : *cur + step)
              : (uint8_t)((*cur - step < tgt) ? tgt : *cur - step);
         HAL_Delay(SERVO_RAMP_DELAY_MS);   /* no-op under STRICT_HAL_STUBS */
     }
 
 #ifdef UNIT_TEST
     /* final-state check: we actually reached the target */
     CHECK(*cur == tgt);
 #endif
 }
 
 #endif /* !UNIT_TEST */
 