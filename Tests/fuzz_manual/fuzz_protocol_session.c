/**
 * @file fuzz_protocol_session.c
 * @brief Persistent-state fuzz target feeding protocol commands from streamed input.
 *
 * @details
 * This harness maintains a single ProtocolContext across the entire fuzz run,
 * replaying incoming bytes as newline- or semicolon-delimited commands. It:
 *   - Initializes the context once in LLVMFuzzerInitialize().
 *   - Ensures authentication and enters the servo submenu before processing.
 *   - Buffers bytes into commands, invoking Protocol_ProcessCommand() on each.
 *   - Immediately executes any queued servo move via Servo_Ramp().
 *   - Resets commandPending and returns to STATE_MENU after each move.
 * This approach exercises stateful parsing, command queuing, and servo
 * ramping logic under continuous, incremental input mutations.
 */

#include "test_common.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static ProtocolContext ctx;   /* persistent context for entire fuzz run */

/* Called once when the fuzzer starts */
int LLVMFuzzerInitialize(int *argc, char ***argv)
{
    (void)argc; (void)argv;
    Protocol_Init(&ctx);
    return 0;
}

/* feed one test-case ------------------------------------------------- */
static void feed_bytes(const uint8_t *buf, size_t sz)
{
    /* Ensure we’re in SERVO entry state before replaying data */
    if (!ctx.authenticated)  Protocol_ProcessCommand(&ctx, "1234");
    if (ctx.state == STATE_MENU) Protocol_ProcessCommand(&ctx, "1");

    char line[64]; size_t pos = 0;

    for (size_t i = 0; i < sz; ++i) {
        char c = (char)buf[i];

        if (c == ';' || c == '\n' || c == '\r') {          /* end-of-command */
            line[pos] = '\0';
            Protocol_ProcessCommand(&ctx, line);
            pos = 0;

            /* execute queued move immediately */
            if (ctx.commandPending) {
                Servo_Ramp(&ctx.current_servo_angle,
                           ctx.pendingTargetAngle,
                           ctx.pendingStep);
                ctx.commandPending = 0;
                ctx.state          = STATE_MENU;
            }
            continue;
        }

        if (pos < sizeof(line) - 1) line[pos++] = c;
    }

    /* trailing chunk */
    if (pos) {
        line[pos] = '\0';
        Protocol_ProcessCommand(&ctx, line);
        if (ctx.commandPending) {
            Servo_Ramp(&ctx.current_servo_angle,
                       ctx.pendingTargetAngle,
                       ctx.pendingStep);
            ctx.commandPending = 0;
            ctx.state          = STATE_MENU;
        }
    }
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    feed_bytes(data, size);
    return 0;
}
