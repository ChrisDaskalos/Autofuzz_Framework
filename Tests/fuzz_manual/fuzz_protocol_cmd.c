/**
 * @file fuzz_protocol_cmd.c
 * @brief Stateless, one-command fuzz target driving menu vs. servo commands.
 *
 * @details
 * This fuzzer harness:
 *   - Uses Protocol_ProcessCommand to drive authentication and command dispatch.
 *   - Treats single-byte inputs as menu commands, multi-byte as servo commands.
 *   - Wraps Servo_Ramp in a 1 s alarm + setjmp to abort on zero-step or infinite loops.
 *   - Overrides checksum validation: any “ANGLE,STEP,…“ line is queued so that
 *     Servo_Ramp is exercised directly.
 *   - Triggers a tiny overflow on unqueued inputs to invoke ASan in Protocol_ProcessCommand.
 *
 * Build flags:
 *   -DUNIT_TEST -DFUZZING -fsanitize=fuzzer,address,undefined
 */

#include "test_common.h"    /* ProtocolContext, Servo_Ramp, etc. */
#include <stdint.h>
#include <string.h>
#include <signal.h>
#include <setjmp.h>
#include <stdio.h>
#include <unistd.h>

static jmp_buf _ramp_jmp;
static void _on_alarm(int sig) 
{
    (void)sig;
    longjmp(_ramp_jmp, 1);
}

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size)
{
    if (Size == 0 || Size > 63)
        return 0;

    /* NUL‐terminate a local buffer */
    char buf[64];
    memcpy(buf, Data, Size);
    buf[Size] = '\0';

    /* 1) fresh context */
    ProtocolContext ctx;
    Protocol_Init(&ctx);

    /* 2) authenticate */
    Protocol_ProcessCommand(&ctx, PROTOCOL_PASSWORD);

    /* 3) dispatch: single‐char => menu, else => servo‐cmd */
    if (Size == 1) 
    {
        Protocol_ProcessCommand(&ctx, buf);
    } 
    else 
    {
        /* enter servo submenu */
        Protocol_ProcessCommand(&ctx, "1");
        /* feed the fuzzed angle,step,checksum (or garbage) */
        Protocol_ProcessCommand(&ctx, buf);

        /* —— FORCE IT THROUGH —— */
        /* parse out two ints (angle, step), ignore checksum */
        int angle = 0, step = 0;
        {
            char *f1 = strtok(buf, ",");
            char *f2 = strtok(NULL, ",");
            if (f1) angle = atoi(f1);
            if (f2) step = atoi(f2);
        }
        /* clamp angle into uint8_t, wrap step as uint8_t */
        if (angle < 0) angle = 0;
        if (angle > 255) angle = 255;
        ctx.pendingTargetAngle = (uint8_t)angle;
        ctx.pendingStep        = (uint8_t)step;
        ctx.commandPending     = 1;
    }

    /* 4) if it queued a move, run the *real* Servo_Ramp under a 1 s watchdog */
    if (ctx.commandPending) 
    {
        ctx.state = STATE_RUNNING;

        signal(SIGALRM, _on_alarm);
        alarm(1);

        if (setjmp(_ramp_jmp) == 0) 
        {
            /* may hang/loop or misbehave — alarm triggers our on_alarm */
            Servo_Ramp(&ctx.current_servo_angle,
                       ctx.pendingTargetAngle,
                       ctx.pendingStep);
        } 
        else 
        {
            /* timed out or infinite‐loop */
            fprintf(stderr,
                    "[FUZZ] Servo_Ramp hung or misbehaved (step=%u)\n",
                    ctx.pendingStep);
            __builtin_trap();
        }

        alarm(0);
        ctx.state = STATE_MENU;
        return 0;
    }

    /* 5) no move queued: nothing more to do.
     *    (A deliberate memcpy(bad, "X", 2) into a 1-byte buffer used to be
     *    here. It made every such input "crash" in the harness itself, not
     *    in the firmware, whenever the compiler did not optimise it away,
     *    e.g. at -O0. Removed so that every finding comes from the
     *    firmware.) */
    return 0;
}
