/*
 * cli.h - a tiny text command interpreter on top of the ring buffer.
 *
 * A script is one or more commands, separated by ';' or a new line:
 *
 *   push <n> [<n> ...]   add bytes (0..255)
 *   pop                  remove the oldest byte
 *   peek <i>             show the byte at position i (0 = oldest)
 *   fill <n>             push the values 0, 1, ..., n-1 (stops when full)
 *   count                show how many bytes are stored
 *   clear                remove everything
 *
 * Part of the AutoFuzz example project (see ../README.md).
 */
#ifndef CLI_H
#define CLI_H

#include <stddef.h>

#define CLI_BUFFER_SIZE 8      /* bytes in the ring buffer */
#define CLI_MAX_LINE    128    /* longer commands are cut */
#define CLI_MAX_OUTPUT  256

/* Results of one command */
enum {
    CLI_OK = 0,
    CLI_ERR_UNKNOWN = -1,      /* unknown command */
    CLI_ERR_ARG = -2,          /* missing or bad number */
    CLI_ERR_FULL = -3,
    CLI_ERR_EMPTY = -4,
};

/* Run one command line (no ';'). Writes a short answer to cli_output(). */
int cli_execute(const char *line);

/* Run a script on an EMPTY ring buffer. Returns the number of commands
 * that failed (0 = all OK). */
int cli_run(const char *script);

/* The answer of the last command. */
const char *cli_output(void);

/* Parse a whole decimal number 0..max. Returns 0, or -1 if it is not one. */
int cli_parse_uint(const char *text, unsigned long max, unsigned long *out);

#endif /* CLI_H */
