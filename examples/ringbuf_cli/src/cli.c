/*
 * cli.c - a tiny text command interpreter on top of the ring buffer.
 * See cli.h for the commands.
 */
#include "cli.h"
#include "ringbuf.h"

#include <ctype.h>
#include <stdio.h>
#include <string.h>

static uint8_t g_storage[CLI_BUFFER_SIZE];
static ringbuf_t g_rb = { g_storage, CLI_BUFFER_SIZE, 0, 0, 0 };
static char g_output[CLI_MAX_OUTPUT];

const char *cli_output(void)
{
    return g_output;
}

int cli_parse_uint(const char *text, unsigned long max, unsigned long *out)
{
    unsigned long value = 0;
    if (text == NULL || out == NULL || *text == '\0') {
        return -1;
    }
    for (; *text != '\0'; text++) {
        if (!isdigit((unsigned char)*text)) {
            return -1;
        }
        value = value * 10 + (unsigned long)(*text - '0');
        if (value > max) {
            return -1;
        }
    }
    *out = value;
    return 0;
}

static int cmd_push(char *args)
{
    int pushed = 0;
    for (char *tok = strtok(args, " \t"); tok != NULL; tok = strtok(NULL, " \t")) {
        unsigned long v;
        if (cli_parse_uint(tok, 255, &v) != 0) {
            return CLI_ERR_ARG;
        }
        if (ringbuf_push(&g_rb, (uint8_t)v) != 0) {
            return CLI_ERR_FULL;
        }
        pushed++;
    }
    snprintf(g_output, sizeof g_output, "pushed %d", pushed);
    return pushed > 0 ? CLI_OK : CLI_ERR_ARG;
}

static int cmd_number_arg(char *args, unsigned long max, unsigned long *out)
{
    char *tok = strtok(args, " \t");
    if (tok == NULL || strtok(NULL, " \t") != NULL) {
        return CLI_ERR_ARG;
    }
    return cli_parse_uint(tok, max, out) == 0 ? CLI_OK : CLI_ERR_ARG;
}

int cli_execute(const char *line)
{
    char buf[CLI_MAX_LINE];
    unsigned long n;
    int v;

    g_output[0] = '\0';
    if (line == NULL) {
        return CLI_ERR_UNKNOWN;
    }
    snprintf(buf, sizeof buf, "%s", line);   /* copy; longer lines are cut */

    char *cmd = buf;
    while (*cmd == ' ' || *cmd == '\t') {
        cmd++;
    }
    char *args = cmd + strcspn(cmd, " \t");
    if (*args != '\0') {
        *args++ = '\0';
    }

    if (strcmp(cmd, "push") == 0) {
        return cmd_push(args);
    }
    if (strcmp(cmd, "pop") == 0) {
        v = ringbuf_pop(&g_rb);
        if (v < 0) {
            return CLI_ERR_EMPTY;
        }
        snprintf(g_output, sizeof g_output, "%d", v);
        return CLI_OK;
    }
    if (strcmp(cmd, "peek") == 0) {
        if (cmd_number_arg(args, CLI_BUFFER_SIZE, &n) != CLI_OK) {
            return CLI_ERR_ARG;
        }
        v = ringbuf_peek(&g_rb, (size_t)n);
        if (v < 0) {
            return CLI_ERR_ARG;
        }
        snprintf(g_output, sizeof g_output, "%d", v);
        return CLI_OK;
    }
    if (strcmp(cmd, "fill") == 0) {
        if (cmd_number_arg(args, 255, &n) != CLI_OK) {
            return CLI_ERR_ARG;
        }
        for (unsigned long i = 0; i < n; i++) {
            if (ringbuf_push(&g_rb, (uint8_t)i) != 0) {
                break;
            }
        }
        snprintf(g_output, sizeof g_output, "%zu", ringbuf_count(&g_rb));
        return CLI_OK;
    }
    if (strcmp(cmd, "count") == 0) {
        snprintf(g_output, sizeof g_output, "%zu", ringbuf_count(&g_rb));
        return CLI_OK;
    }
    if (strcmp(cmd, "clear") == 0) {
        ringbuf_clear(&g_rb);
        return CLI_OK;
    }
    return CLI_ERR_UNKNOWN;
}

int cli_run(const char *script)
{
    int failed = 0;
    ringbuf_init(&g_rb, g_storage, sizeof g_storage);
    if (script == NULL) {
        return 0;
    }
    while (*script != '\0') {
        size_t len = strcspn(script, ";\n");
        char line[CLI_MAX_LINE];
        size_t keep = len < sizeof line - 1 ? len : sizeof line - 1;
        memcpy(line, script, keep);
        line[keep] = '\0';
        if (keep > 0 && cli_execute(line) != CLI_OK) {
            failed++;
        }
        script += len;
        if (*script != '\0') {
            script++;
        }
    }
    return failed;
}
