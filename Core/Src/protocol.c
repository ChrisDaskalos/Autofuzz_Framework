#ifdef UNIT_TEST
	#include "test_common.h"
#else
	#include "protocol.h"
	#include "servo.h"
	#include <stdio.h>
	#include <string.h>
	#include <stdlib.h>
	#include "protocol_defs.h"
	#include "servo_defs.h"
#endif

// Global definition of protocol context.
ProtocolContext protocol_ctx;

void Protocol_ProcessCommand(ProtocolContext *ctx, char *command)
{
    // Strip trailing newline characters.
    for (char *p = command; *p; p++) {
        if (*p == '\r' || *p == '\n') {
            *p = '\0';
            break;
        }
    }
    if (command[0] == '\0')
        return;

    if (!ctx->authenticated)
    {
        if (strcmp(command, PROTOCOL_PASSWORD) == 0) {
            HAL_UART_Transmit(&huart2, (uint8_t*)PASSWORD_ACCEPTED_MSG, strlen(PASSWORD_ACCEPTED_MSG), UART_TX_TIMEOUT);
            ctx->authenticated = 1;
            ctx->state = STATE_MENU;
            strcpy(ctx->diagnostic_info, "AUTHENTICATED.");
            Protocol_DisplayMenu();
        } else {
            HAL_UART_Transmit(&huart2, (uint8_t*)INVALID_PASSWORD_MSG, strlen(INVALID_PASSWORD_MSG), UART_TX_TIMEOUT);
            strcpy(ctx->diagnostic_info, "AUTHENTICATION FAILED.");
        }
        return;
    }

    // While a ramp is running, only allow cancellation.
    if (ctx->state == STATE_RUNNING)
    {
        if (strlen(command) == 1 && (command[0]=='B' || command[0]=='b'))
        {
            ctx->cancelRequested = 1;
            HAL_UART_Transmit(&huart2, (uint8_t*)"CANCELLATION REQUESTED.\r\n", 26, UART_TX_TIMEOUT);
        }
        return;
    }

    // Process menu selections.
    if (ctx->state == STATE_MENU && strlen(command) == 1)
    {
        switch(command[0])
        {
            case '1':
            {
                HAL_UART_Transmit(&huart2, (uint8_t*)SERVO_CMD_PROMPT, strlen(SERVO_CMD_PROMPT), UART_TX_TIMEOUT);
                ctx->state = STATE_WAIT_SERVO;
                return;
            }
            case '2':
            {
                // Shutdown: reset to default angle.
                Servo_SetAngle(SERVO_DEFAULT_ANGLE);
                ctx->current_servo_angle = SERVO_DEFAULT_ANGLE;
                HAL_UART_Transmit(&huart2, (uint8_t*)MOTOR_SHUTDOWN_MSG, strlen(MOTOR_SHUTDOWN_MSG), UART_TX_TIMEOUT);
                Protocol_DisplayMenu();
                return;
            }
            case '3':
            {
                char statMsg[150];
                sprintf(statMsg, "\r\nSTATUS: ANGLE=%d, DIAG=%s\r\n",
                        ctx->current_servo_angle, ctx->diagnostic_info);
                HAL_UART_Transmit(&huart2, (uint8_t*)statMsg, strlen(statMsg), UART_TX_TIMEOUT);
                Protocol_DisplayMenu();
                return;
            }
            case '4':
            {
                Protocol_DisplayHelp();
                Protocol_DisplayMenu();
                return;
            }
            default:
            {
                HAL_UART_Transmit(&huart2, (uint8_t*)UNKNOWN_MENU_OPTION_MSG, strlen(UNKNOWN_MENU_OPTION_MSG), UART_TX_TIMEOUT);
                Protocol_DisplayMenu();
                return;
            }
        }
    }

    // Process servo command input in format: ANGLE,STEP,CHECKSUM.
    if (ctx->state == STATE_WAIT_SERVO)
    {
        if (command[0]=='(' && command[strlen(command)-1]==')')
        {
            command[strlen(command)-1] = '\0';
            command++;
        }

        char *field1 = strtok(command, ",");
        char *field2 = strtok(NULL, ",");
        char *field3 = strtok(NULL, ",");

        if (!field1 || !field2 || !field3)
        {
            HAL_UART_Transmit(&huart2, (uint8_t*)"FORMAT ERROR: MUST BE ANGLE,STEP,CHECKSUM\r\n", 43, UART_TX_TIMEOUT);
            ctx->state = STATE_MENU;
            Protocol_DisplayMenu();
            return;
        }

        int angle = atoi(field1);
        int step = atoi(field2);
        int userCksum = atoi(field3);
        uint8_t compCksum = ComputeChecksumFromNumbers(angle, step);

        char dbg[80];
        sprintf(dbg, "\r\nCOMMAND RECEIVED: %d,%d,%d => COMP=%d\r\n", angle, step, userCksum, compCksum);
        HAL_UART_Transmit(&huart2, (uint8_t*)dbg, strlen(dbg), UART_TX_TIMEOUT);

        if (userCksum != compCksum)
        {
            HAL_UART_Transmit(&huart2, (uint8_t*)CHECKSUM_ERROR_MSG, strlen(CHECKSUM_ERROR_MSG), UART_TX_TIMEOUT);
            ctx->state = STATE_MENU;
            Protocol_DisplayMenu();
            return;
        }

        if (angle > SERVO_MAX_ANGLE)
            angle = SERVO_MAX_ANGLE;

        // Queue the servo command to be executed in main loop.
        ctx->pendingTargetAngle = (uint8_t)angle;
        ctx->pendingStep = (uint8_t)step;
        ctx->commandPending = 1;

        HAL_UART_Transmit(&huart2, (uint8_t*)CMD_QUEUED_MSG, strlen(CMD_QUEUED_MSG), UART_TX_TIMEOUT);
        return;
    }

    Protocol_DisplayMenu();
}

uint8_t ComputeChecksumFromNumbers(int angle, int step)
{
    return (uint8_t)(angle + step);
}

void Protocol_DisplayMenu(void)
{
    HAL_UART_Transmit(&huart2, (uint8_t*)MENU_PROMPT, strlen(MENU_PROMPT), UART_TX_TIMEOUT);
}

void Protocol_DisplayHelp(void)
{
    HAL_UART_Transmit(&huart2, (uint8_t*)HELP_MESSAGE, strlen(HELP_MESSAGE), UART_TX_TIMEOUT);
}

void Protocol_Init(ProtocolContext *ctx)
{
    ctx->authenticated = 0;
    ctx->current_servo_angle = SERVO_DEFAULT_ANGLE;
    ctx->state = STATE_MENU;
    ctx->cancelRequested = 0;
    ctx->pendingTargetAngle = 0;
    ctx->pendingStep = 0;
    ctx->commandPending = 0;
    strcpy(ctx->diagnostic_info, "AWAITING PASSWORD.");

    HAL_UART_Transmit(&huart2, (uint8_t*)WELCOME_MSG, strlen(WELCOME_MSG), UART_TX_TIMEOUT);
}


