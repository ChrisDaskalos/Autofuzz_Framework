#include "test_common.h"

TIM_HandleTypeDef htim2 = (TIM_HandleTypeDef){0};
UART_HandleTypeDef huart2 = (UART_HandleTypeDef){0};


void HAL_Delay(uint32_t ms) { (void)ms; }

static const char FORMAT_ERROR_MSG[] = "Error: Invalid format\r\n";
static const char CANCEL_MSG[]       = "Command cancelled\r\n";

#define TRIM_INPLACE(p) do{ while(*(p)==' '||*(p)=='\t') ++(p); }while(0)
#define IS_CANCEL(c)    ( ((c)[0]=='B'||(c)[0]=='b') && (c)[1]=='\0' )

void reset_ctx(ProtocolContext *c)
{
    if (!c) return;
    c->authenticated       = 0;
    c->current_servo_angle = SERVO_DEFAULT_ANGLE;
    c->state               = STATE_MENU;
    c->cancelRequested     = 0;
    c->pendingTargetAngle  = 0;
    c->pendingStep         = 0;
    c->commandPending      = 0;
    strcpy(c->diagnostic_info, "AWAITING PASSWORD.");

    HAL_UART_Transmit(&huart2, (uint8_t*)WELCOME_MSG, (uint16_t)strlen(WELCOME_MSG), UART_TX_TIMEOUT);
}

void Protocol_Init(ProtocolContext *ctx) { reset_ctx(ctx); }

static void handle_menu(ProtocolContext *c, char sel)
{
    switch (sel)
    {
        case '1':
            HAL_UART_Transmit(&huart2, (uint8_t*)SERVO_CMD_PROMPT, (uint16_t)strlen(SERVO_CMD_PROMPT), UART_TX_TIMEOUT);
            c->state = STATE_WAIT_SERVO;
            return;
        case '2':
            Servo_SetAngle(SERVO_DEFAULT_ANGLE);
            c->current_servo_angle = SERVO_DEFAULT_ANGLE;
            HAL_UART_Transmit(&huart2, (uint8_t*)MOTOR_SHUTDOWN_MSG, (uint16_t)strlen(MOTOR_SHUTDOWN_MSG), UART_TX_TIMEOUT);
            break;
        case '3': {
            char status[64];
            int n = snprintf(status, sizeof(status), "STATUS: angle=%u\r\n", (unsigned)c->current_servo_angle);
            if (n > 0) HAL_UART_Transmit(&huart2, (uint8_t*)status, (uint16_t)n, UART_TX_TIMEOUT);
            break;
        }
        case '4':
            HAL_UART_Transmit(&huart2, (uint8_t*)HELP_MESSAGE, (uint16_t)strlen(HELP_MESSAGE), UART_TX_TIMEOUT);
            break;
        default:
            HAL_UART_Transmit(&huart2, (uint8_t*)UNKNOWN_MENU_OPTION_MSG, (uint16_t)strlen(UNKNOWN_MENU_OPTION_MSG), UART_TX_TIMEOUT);
            break;
    }
    Protocol_DisplayMenu();
    c->state = STATE_MENU;
}

/* Keep helper local so fuzz doesn’t target raw pointer/size-less APIs */
static int ascii_to_int(const char *s, int *out)
{
    if (!s || !out) return 0;
    while (*s==' '||*s=='\t') ++s;
    char *end;
    long v = strtol(s, &end, 10);
    while (*end==' '||*end=='\t') ++end;
    if (*end!='\0') return 0;
    *out = (int)v;
    return 1;
}

static void handle_servo_cmd(ProtocolContext *c, char *cmd)
{
    TRIM_INPLACE(cmd);
    if (*cmd=='(') { ++cmd; char *r=strrchr(cmd,')'); if (r) *r='\0'; }

    char *a = strtok(cmd,",");
    char *b = strtok(NULL,",");
    char *k = strtok(NULL,",");
    if (!a||!b||!k) {
        HAL_UART_Transmit(&huart2, (uint8_t*)FORMAT_ERROR_MSG,(uint16_t)strlen(FORMAT_ERROR_MSG), UART_TX_TIMEOUT);
        c->state=STATE_MENU; Protocol_DisplayMenu(); return;
    }

    int angle, step, cks;
    if (!ascii_to_int(a,&angle) || !ascii_to_int(b,&step) || !ascii_to_int(k,&cks)) {
        HAL_UART_Transmit(&huart2, (uint8_t*)FORMAT_ERROR_MSG, (uint16_t)strlen(FORMAT_ERROR_MSG), UART_TX_TIMEOUT);
        c->state=STATE_MENU; Protocol_DisplayMenu(); return;
    }

    if ((uint8_t)(angle + step) != (uint8_t)cks) {
        HAL_UART_Transmit(&huart2, (uint8_t*)CHECKSUM_ERROR_MSG, (uint16_t)strlen(CHECKSUM_ERROR_MSG), UART_TX_TIMEOUT);
        c->state=STATE_MENU; Protocol_DisplayMenu(); return;
    }

    if (angle > SERVO_MAX_ANGLE) angle = SERVO_MAX_ANGLE; /* no lower clamp by design */
    /* no step validation by design */

    c->pendingTargetAngle = (uint8_t)angle;
    c->pendingStep        = (uint8_t)step;
    c->commandPending     = 1;
    c->state              = STATE_WAIT_SERVO;

    HAL_UART_Transmit(&huart2, (uint8_t*)CMD_QUEUED_MSG, (uint16_t)strlen(CMD_QUEUED_MSG), UART_TX_TIMEOUT);
}

void Protocol_ProcessCommand(ProtocolContext *ctx, char *cmd_raw)
{
    if (!ctx || !cmd_raw) return;

    /* Copy up to CR/LF into a DMA-sized buffer.
       If no CR/LF and input >= DMA_BUFFER_SIZE, intentionally leave buf unterminated
       to emulate DMA “no NUL” cases (strcmp() below can trip ASan/UB). */
    char buf[DMA_BUFFER_SIZE];
    size_t i = 0;
    for (; i < sizeof(buf); ++i) {
        char ch = cmd_raw[i];
        if (ch=='\0' || ch=='\r' || ch=='\n') break;
        buf[i] = ch;
    }
    if (i < sizeof(buf)) buf[i] = '\0'; /* NUL only if space left or CR/LF found */

    if (ctx->state==STATE_RUNNING && IS_CANCEL(buf)) {
        ctx->cancelRequested = 1;
        HAL_UART_Transmit(&huart2, (uint8_t*)CANCEL_MSG, (uint16_t)strlen(CANCEL_MSG), UART_TX_TIMEOUT);
        return;
    }

    if (!ctx->authenticated) {
        if (strcmp(buf, PROTOCOL_PASSWORD)==0) { /* may read past if buf not NUL-terminated (intentional) */
            ctx->authenticated=1; ctx->state=STATE_MENU;
            HAL_UART_Transmit(&huart2, (uint8_t*)PASSWORD_ACCEPTED_MSG, (uint16_t)strlen(PASSWORD_ACCEPTED_MSG), UART_TX_TIMEOUT);
            Protocol_DisplayMenu();
        } else {
            HAL_UART_Transmit(&huart2, (uint8_t*)INVALID_PASSWORD_MSG, (uint16_t)strlen(INVALID_PASSWORD_MSG), UART_TX_TIMEOUT);
        }
        return;
    }

    if (ctx->state==STATE_MENU && strlen(buf)==1)
        return handle_menu(ctx, buf[0]);

    if (ctx->state==STATE_WAIT_SERVO)
        return handle_servo_cmd(ctx, buf);
}

void Protocol_DisplayMenu(void)
{
    HAL_UART_Transmit(&huart2, (uint8_t*)MENU_PROMPT, (uint16_t)strlen(MENU_PROMPT), UART_TX_TIMEOUT);
}

void Protocol_DisplayHelp(void)
{
    HAL_UART_Transmit(&huart2, (uint8_t*)HELP_MESSAGE, (uint16_t)strlen(HELP_MESSAGE), UART_TX_TIMEOUT);
}

uint8_t ComputeChecksumFromNumbers(int a, int b)
{
    return (uint8_t)(a + b); /* keep UB so UBSan flags it */
}

void Servo_SetAngle(uint8_t a) { (void)a; }
void Servo_Init(void) { Servo_SetAngle(SERVO_DEFAULT_ANGLE); }

static void Servo_Ramp_impl(uint8_t *cur, uint8_t tgt, uint8_t step)
{
    if (!cur || step==0) return;
    while (*cur != tgt)
    {
        if (*cur < tgt) *cur = (uint8_t)((*cur + step > tgt) ? tgt : *cur + step);
        else            *cur = (uint8_t)((*cur < step)       ? tgt : *cur - step);
        HAL_Delay(1);
    }
}

uint8_t Servo_Ramp_safe(uint8_t cur, uint8_t tgt, uint8_t step)
{
    uint8_t shadow = cur;
    Servo_Ramp_impl(&shadow, tgt, step);
    return shadow;
}
