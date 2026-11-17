/*  fuzz_custom_mutator.c   (safe version) */
/**
 * @file fuzz_custom_mutator.c
 * @brief Safe custom mutator and crossover hooks for protocol fuzzing.
 *
 * @details
 * This source file provides customized mutation and crossover functions
 * for use with libFuzzer when fuzzing the protocol command parser.
 * It includes:
 *   - A safe checksum function `ck()` that avoids signed overflow.
 *   - `good_cmd()` to generate well-formed servo commands.
 *   - `evil_cmd()` to produce deliberately malformed commands for edge cases.
 *   - `build_session()` to assemble a login-session sequence with a mix of
 *     valid and invalid commands.
 *   - `LLVMFuzzerCustomMutator()` to choose between generating whole sessions,
 *     single commands, or delegating to the built-in mutator.
 *   - `LLVMFuzzerCustomCrossOver()` to perform a safe crossover by copying
 *     from one parent without overflowing the output buffer.
 *
 * These hooks ensure robust fuzz-testing of authentication, command parsing,
 * checksum validation, and boundary conditions without undefined behavior.
 */

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "protocol_defs.h"
#include "servo_defs.h"

/* ------------------------------------------------------------------ */
/* safe checksum – no signed-overflow UB */
/* The unsigned wrap-around is intended; tell -fsanitize=integer so it
 * does not report the mutator itself as a finding. */
__attribute__((no_sanitize("unsigned-integer-overflow")))
static inline uint8_t ck(int a, int s)
{
    uint32_t sum = (uint32_t)a + (uint32_t)s;   /* unsigned add */
    return (uint8_t)(sum & 0xFF);
}

/* ---------- command builders -------------------------------------- */
static size_t good_cmd(char *d, size_t max, unsigned *seed)
{
    int a = rand_r(seed) % (SERVO_MAX_ANGLE + 1);   /* 0-165  */
    int s = 1 + rand_r(seed) % SERVO_MAX_STEP;      /* 1-45   */
    return (size_t)snprintf(d, max, "%d,%d,%u\n", a, s, ck(a, s));
}

static size_t evil_cmd(char *d, size_t max, unsigned *seed)
{
    /* deliberately malformed variants */
    static const struct { int a, s; } cases[] = {
        { -1,             5  },   /* negative angle          */
        { 166,            5  },   /* angle  > MAX            */
        { 90,             0  },   /* step   = 0              */
        { 90,             46 },   /* step   > MAX            */
        { 0x7FFFFFFF,     1  }    /* huge → checksum corner  */
    };
    const char *delims[] = { ",", ";", " ", ")\n" };
    const int idx  = rand_r(seed) % 5;
    const char *dl = delims[rand_r(seed) % 4];
    unsigned bad   = ck(cases[idx].a, cases[idx].s) ^ 0x5A;
    return (size_t)snprintf(d, max, "%d%s%d%s%u\n",
                             cases[idx].a, dl,
                             cases[idx].s, dl,
                             bad);
}

/* ---------- session builder --------------------------------------- */
static size_t build_session(uint8_t *Data, size_t Max, unsigned Seed)
{
    char   *p   = (char *)Data;
    size_t  rem = Max;

    size_t n = snprintf(p, rem, PROTOCOL_PASSWORD "\n1\n");
    p += n; rem -= n;

    int cycles = 3 + rand_r(&Seed) % 10;          /* 3–12 cmds */
    for (int i = 0; i < cycles && rem > 40; ++i) {
        n = (rand_r(&Seed) % 4) ?                       /* 75 % good */
              good_cmd(p, rem, &Seed)
            : evil_cmd(p, rem, &Seed);                  /* 25 % evil */
        p += n; rem -= n;
    }
    return (size_t)(p - (char *)Data);
}

/* ---------- exported hooks ---------------------------------------- */
size_t LLVMFuzzerCustomMutator(uint8_t *Data, size_t Size,
                               size_t MaxSize, unsigned Seed)
{
    unsigned pick = rand_r(&Seed) % 20;

    if (pick < 12)                         /* 60 % login-session  */
        return build_session(Data, MaxSize, Seed);

    if (pick < 17) {                       /* 25 % single command */
        return (rand_r(&Seed) & 1)
               ? good_cmd((char *)Data, MaxSize, &Seed)
               : evil_cmd((char *)Data, MaxSize, &Seed);
    }

    /* 15 %: havoc via builtin mutator */
    extern size_t LLVMFuzzerMutate(uint8_t*,size_t,size_t);
    return LLVMFuzzerMutate(Data, Size, MaxSize);
}

/* ---------- safe cross-over (no overflow) ------------------------- */
size_t LLVMFuzzerCustomCrossOver(const uint8_t *D1, size_t S1,
                                 const uint8_t *D2, size_t S2,
                                 uint8_t *Out, size_t Max,
                                 unsigned Seed)
{
    const uint8_t *src;
    size_t         len_src;

    if (Seed & 1) { src = D1; len_src = S1; }
    else          { src = D2; len_src = S2; }

    size_t len = (len_src > Max) ? Max : len_src;
    memcpy(Out, src, len);
    return len;
}

#ifdef __cplusplus
}
#endif
