/*-----------------------------------------------------------------------------
 * autofuzz_rt.h
 *---------------------------------------------------------------------------*/
#ifndef AUTOFUZZ_RT_H
#define AUTOFUZZ_RT_H

#include <cmocka.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>

/**
 * @brief Run a function in a child process and assert that it aborts.
 *
 * The helper succeeds when:
 *   1. fork(2) returns successfully, and
 *   2. the child terminates via SIGABRT, and
 *   3. the parent observes that termination through waitpid(2).
 *
 * If the child ever returns from @p fn without aborting, we exit with
 * EXIT_FAILURE so the parent records the failure.
 *
 * On non-POSIX hosts the helper is disabled and will assert-fail immediately.
 */
static inline __attribute__((unused))
void expect_abort(void (*fn)(void))
{
#if defined(__unix__)
    pid_t child_pid = fork();
    assert_true(child_pid >= 0);

    if (child_pid == 0)
    {
        /* Child: execute target.  If it returns, treat that as a hard error. */
        fn();
        _exit(EXIT_FAILURE);          /* <-- was _exit(0) */
    }

    int status = 0;
    waitpid(child_pid, &status, 0);

    assert_true(WIFSIGNALED(status));
    assert_int_equal(WTERMSIG(status), SIGABRT);
#else
    /* Fallback for non-POSIX toolchains (e.g. MSVC, MinGW) */
    assert_true(!"expect_abort() not supported on this platform");
#endif
}

#endif /* AUTOFUZZ_RT_H */
