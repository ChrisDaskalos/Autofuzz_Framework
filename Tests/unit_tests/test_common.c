/*  test_common.c  ─ single stub implementation used when UNIT_TEST is set  */
#include "test_common.h"

/* ─── fake peripherals so firmware links ---------------------------------- */
TIM_HandleTypeDef htim2 = {0};
UART_HandleTypeDef huart2 = {0};

void HAL_Delay(uint32_t ms) { (void)ms; }   /* no-op */

/* ───────────────────────────────────────────────────────────────────────── */
/*  PROTOCOL  (just enough logic to satisfy **all** current unit-tests)     */
/* ───────────────────────────────────────────────────────────────────────── */
/* test_common.c – replace the old TRIM line with: */
#define TRIM_INPLACE(p)   do{ while (*(p)==' ' || *(p)=='\t') ++(p); }while(0)

#define IS_CANCEL(c)   ((c)[0]=='B'||(c)[0]=='b') && (c)[1]=='\0'


void reset_ctx(ProtocolContext *c)
{
    c->authenticated      = 0;
    c->current_servo_angle= SERVO_DEFAULT_ANGLE;
    c->state              = STATE_MENU;
    c->cancelRequested    = 0;
    c->pendingTargetAngle = 0;
    c->pendingStep        = 0;
    c->commandPending     = 0;
    strcpy(c->diagnostic_info,"AWAITING PASSWORD.");
}

void Protocol_Init(ProtocolContext *ctx)          { reset_ctx(ctx); }

static void handle_menu(ProtocolContext *c,char sel)
{
    switch (sel)
    {
        case '1': c->state = STATE_WAIT_SERVO;                          break;
        case '2': c->current_servo_angle = SERVO_DEFAULT_ANGLE;         break;
        case '3': /* status – nothing to mutate */                      break;
        case '4': /* help   – nothing to mutate */                      break;
        default : /* unknown -> stay in menu            */              break;
    }
    c->state = STATE_MENU;   /* every path ends back at menu              */
}

/* 0 = parse failure, 1 = success */
int ascii_to_int(const char *s, int *out)
{
    /* --- extra guards so fuzzers can’t crash us ---------------------- */
    if (!s || !out)                       /* NULL pointer passed in?   */
        return 0;
    if (*s == '\0')                       /* empty string ⇒ failure    */
        return 0;

    char *end;
    long v = strtol(s, &end, 10);

    /* reject if any trailing junk remains */
    if (*end != '\0')
        return 0;

    *out = (int)v;
    return 1;
}


static void handle_servo_cmd(ProtocolContext *c,char *cmd)
{
    /* optional wrapping parentheses & surrounding WS */
    TRIM_INPLACE(cmd);
    if (*cmd=='(') { ++cmd; char *r=strrchr(cmd,')'); if (r) *r='\0'; }

    char *a = strtok(cmd,",");
    char *b = strtok(NULL,",");
    char *k = strtok(NULL,",");
    if (!a||!b||!k) { c->state=STATE_MENU; return; }

    int angle,step,cks;               /* validate ints */
    if (!ascii_to_int(a,&angle)||
        !ascii_to_int(b,&step)||
        !ascii_to_int(k,&cks))
    { c->state=STATE_MENU; return; }

    if (angle > SERVO_MAX_ANGLE) angle = SERVO_MAX_ANGLE;

    if ((uint8_t)(angle+step) != (uint8_t)cks || step<=0)
    { c->state=STATE_MENU; return; }

    c->pendingTargetAngle = (uint8_t)angle;
    c->pendingStep        = (uint8_t)step;
    c->commandPending     = 1;
    c->state              = STATE_WAIT_SERVO;   /* remains until main loop */
}

void Protocol_ProcessCommand(ProtocolContext *ctx,char *cmd_raw)
{
    /* strip trailing CR/LF and copy to scratch buffer */
    char buf[64];
    size_t n = strcspn(cmd_raw, "\r\n");
    strncpy(buf, cmd_raw, n); buf[n] = '\0';

    char *p = buf;          /* << make it an l-value pointer   */
    TRIM_INPLACE(p);

    /* handle cancel during ramp */
    if (ctx->state==STATE_RUNNING && IS_CANCEL(buf))
    { ctx->cancelRequested = 1; return; }

    /* authentication gate */
    if (!ctx->authenticated)
    {
        if (strcmp(buf,PROTOCOL_PASSWORD)==0)
        { ctx->authenticated=1; ctx->state=STATE_MENU; }
        return;
    }

    /* state-specific handlers */
    if (ctx->state==STATE_MENU && strlen(buf)==1)
        return handle_menu(ctx,buf[0]);
    if (ctx->state==STATE_WAIT_SERVO)
        return handle_servo_cmd(ctx,buf);
}

void Protocol_DisplayMenu(void)  { /* stub: nothing */ }
void Protocol_DisplayHelp(void)  { /* stub: nothing */ }

/* checksum used by original test */
uint8_t ComputeChecksumFromNumbers(int a,int b){ return (uint8_t)(a+b); }

/* ───────────────────────────────────────────────────────────────────────── */
/*  SERVO  (tiny host-only behaviour)                                       */
/* ───────────────────────────────────────────────────────────────────────── */
void Servo_SetAngle(uint8_t a){ (void)a; }    /* host: ignore PWM */
void Servo_Init(void)      { Servo_SetAngle(SERVO_DEFAULT_ANGLE); }

void Servo_Ramp(uint8_t *cur,uint8_t tgt,uint8_t step)
{
    if (!cur||step==0) return;
    while (*cur!=tgt)
    {
        if (*cur<tgt) *cur = (*cur+step>tgt)?tgt:*cur+step;
        else          *cur = (*cur<step)    ?tgt:*cur-step;
        HAL_Delay(1);
    }
}
