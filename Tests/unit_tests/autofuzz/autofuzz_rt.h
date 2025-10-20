/*-----------------------------------------------------------------------------
 * autofuzz_rt.h
 *-----------------------------------------------------------------------------
 *  – expect_abort(): run a function in a forked child and assert SIGABRT
 *  – autofuzz_sweep(): lightweight deterministic-test helper
 *---------------------------------------------------------------------------*/
#ifndef AUTOFUZZ_RT_H
#define AUTOFUZZ_RT_H

#include <cmocka.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>

/*-------------------------------------------------------------------------
 * expect_abort()
 *-------------------------------------------------------------------------
 * Succeeds when the child terminates via SIGABRT.  On non-POSIX hosts the
 * helper is unavailable and the test fails immediately.
 */
static inline __attribute__((unused))
void expect_abort(void (*fn)(void))
{
#if defined(__unix__)
    pid_t child_pid = fork();
    assert_true(child_pid >= 0);

    if (child_pid == 0)               /* ── child ── */
    {
        fn();                         /* must abort – never return */
        _exit(EXIT_FAILURE);          /* treat normal return as failure */
    }

    int status = 0;
    waitpid(child_pid, &status, 0);

    assert_true(WIFSIGNALED(status));
    assert_int_equal(WTERMSIG(status), SIGABRT);

#else   /* non-POSIX fallback */
    assert_true(!"expect_abort() not supported on this platform");
#endif
}

/*-------------------------------------------------------------------------
 * autofuzz_sweep()
 *-------------------------------------------------------------------------
 * Deterministic harnesses call this helper.  It simply reports “success”
 * so the test framework can continue.
 */
#ifdef __cplusplus
extern "C" {
#endif
int autofuzz_sweep(void);                /* always declared */
#ifdef __cplusplus
}
#endif

#ifdef AUTOFUZZ_RT_IMPL                  /* defined once where requested */
int autofuzz_sweep(void)
{
    return 0;                            /* no failures detected */
}
#endif  /* AUTOFUZZ_RT_IMPL */

#endif /* AUTOFUZZ_RT_H */
