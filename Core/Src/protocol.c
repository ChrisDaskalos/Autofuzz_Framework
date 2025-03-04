#include "protocol.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

// The correct password stored in flash.
static const char CORRECT_PASSWORD[] = "1234";

// Compute checksum as (angle + step) modulo 256.
uint8_t ComputeChecksumFromNumbers(int angle, int step)
{
    return (uint8_t)(angle + step);
}


// Display the main menu in all caps
void Protocol_DisplayMenu(void)
{
    char menuMsg[128];
    snprintf(menuMsg, sizeof(menuMsg),
        "\r\nMENU:\r\n"
        "1. SET SERVO ANGLE\r\n"
        "2. SHUTDOWN MOTOR\r\n"
        "3. DISPLAY STATUS\r\n"
        "4. HELP\r\n"
        "ENTER YOUR CHOICE: ");
    HAL_UART_Transmit(&huart2, (uint8_t*)menuMsg, strlen(menuMsg), 100);
}

// Display the detailed help in all caps
void Protocol_DisplayHelp(void)
{
    char helpMsg[512];
    snprintf(helpMsg, sizeof(helpMsg),
        "\r\n***** DETAILED HELP *****\r\n"
        "OPTION 1: SET SERVO ANGLE\r\n"
        "   ENTER A COMMAND IN THE FORMAT: ANGLE,STEP,CHECKSUM\r\n"
        "   ANGLE IN [0..165] (CLAMPED IF ABOVE 165)\r\n"
        "   STEP (E.G., 5)\r\n"
        "   CHECKSUM = (ANGLE + STEP) MOD 256\r\n"
        "\r\n   EXAMPLE: 90,5,95\r\n"
        "OPTION 2: SHUTDOWN MOTOR\r\n"
        "   RESETS SERVO TO 90 DEGREES.\r\n"
        "OPTION 3: DISPLAY STATUS\r\n"
        "OPTION 4: HELP\r\n"
        "\r\nPRESS 'B' ANYTIME DURING A RAMP TO CANCEL AND RETURN TO MENU.\r\n"
        "******************************\r\n");
    HAL_UART_Transmit(&huart2, (uint8_t*)helpMsg, strlen(helpMsg), 100);
}

void Protocol_Init(ProtocolContext *ctx)
{
    ctx->authenticated = 0;
    ctx->current_servo_angle = 90;
    ctx->state = STATE_MENU;
    ctx->cancelRequested = 0;
    ctx->pendingTargetAngle = 0;
    ctx->pendingStep = 0;
    ctx->commandPending = 0;
    strcpy(ctx->diagnostic_info, "AWAITING PASSWORD.");

    char welcome[] = "\r\nWELCOME. PLEASE ENTER PASSWORD:\r\n";
    HAL_UART_Transmit(&huart2, (uint8_t*)welcome, strlen(welcome), 100);
}


// Hard‐fix: always attempt to set the servo angle, no matter what
uint8_t Protocol_SetServoAngle(ProtocolContext *ctx, uint8_t angle)
{
    // Clamp the angle to 165
    if (angle > 165)
    {
        angle = 165;
    }

    // DEBUG: Print the old and new angles so we can see if it’s “really” no change.
    char dbg[80];
    sprintf(dbg, "\r\n[DEBUG] CURRENT_ANGLE=%d, REQUESTED=%d\r\n", ctx->current_servo_angle, angle);
    HAL_UART_Transmit(&huart2, (uint8_t*)dbg, strlen(dbg), 100);

    // Map 0° -> 500 and 165° -> 2500
    uint16_t pulse = 500 + ((angle * 2000) / 165);
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, pulse);

    // Update the stored angle
    ctx->current_servo_angle = angle;

    char setMsg[60];
    sprintf(setMsg, "SERVO ANGLE SET TO: %d (PULSE: %d)\r\n", angle, pulse);
    HAL_UART_Transmit(&huart2, (uint8_t*)setMsg, strlen(setMsg), 100);

    strcpy(ctx->diagnostic_info, "SERVO ANGLE UPDATED SUCCESSFULLY.");
    return 0;
}

// Hard‐fix ramp: we always run the ramp, even if the servo angle is the same
void Protocol_RunCommand(ProtocolContext *ctx, uint8_t targetAngle, uint8_t step)
{
    ctx->state = STATE_RUNNING;
    ctx->cancelRequested = 0;

    if (targetAngle > 165)
        targetAngle = 165;

    uint8_t current = ctx->current_servo_angle;

    char dbg[80];
    sprintf(dbg, "\r\n[DEBUG] RAMP FROM %d TO %d STEP=%d\r\n", current, targetAngle, step);
    HAL_UART_Transmit(&huart2, (uint8_t*)dbg, strlen(dbg), 100);

    // If the target is the same as the current angle, force an update.
    if (current == targetAngle)
    {
        Protocol_SetServoAngle(ctx, targetAngle);
    }
    else if (current < targetAngle)
    {
        while (current < targetAngle)
        {
            if (ctx->cancelRequested)
            {
                char cancelMsg[] = "\r\nOPERATION CANCELLED. BACK TO MENU.\r\n";
                HAL_UART_Transmit(&huart2, (uint8_t*)cancelMsg, strlen(cancelMsg), 100);
                ctx->state = STATE_MENU;
                Protocol_DisplayMenu();
                return;
            }
            uint8_t newAngle = (current + step > targetAngle) ? targetAngle : (current + step);
            Protocol_SetServoAngle(ctx, newAngle);
            HAL_Delay(25);
            current = newAngle;
        }
    }
    else // current > targetAngle
    {
        while (current > targetAngle)
        {
            if (ctx->cancelRequested)
            {
                char cancelMsg[] = "\r\nOPERATION CANCELLED. BACK TO MENU.\r\n";
                HAL_UART_Transmit(&huart2, (uint8_t*)cancelMsg, strlen(cancelMsg), 100);
                ctx->state = STATE_MENU;
                Protocol_DisplayMenu();
                return;
            }
            uint8_t newAngle = (current < step) ? targetAngle : current - step;
            if (newAngle < targetAngle)
                newAngle = targetAngle;
            Protocol_SetServoAngle(ctx, newAngle);
            HAL_Delay(25);
            current = newAngle;
        }
    }
    ctx->state = STATE_MENU;
    char doneMsg[] = "\r\nCOMMAND EXECUTED. BACK TO MENU.\r\n";
    HAL_UART_Transmit(&huart2, (uint8_t*)doneMsg, strlen(doneMsg), 100);
    Protocol_DisplayMenu();
}


void Protocol_ProcessCommand(ProtocolContext *ctx, char *command)
{
	// Strip trailing newlines.
	    for (char *p = command; *p; p++)
	    {
	        if (*p == '\r' || *p == '\n')
	        {
	            *p = '\0';
	            break;
	        }
	    }

	    // Ignore empty commands.
	    if(command[0] == '\0')
	        return;

	    // If not authenticated, treat this as a password.
	    if (!ctx->authenticated)
	    {
	        if (strcmp(command, CORRECT_PASSWORD) == 0)
	        {
	            char successMsg[] = "\r\nPASSWORD ACCEPTED!\r\n";
	            HAL_UART_Transmit(&huart2, (uint8_t*)successMsg, strlen(successMsg), 100);
	            ctx->authenticated = 1;
	            ctx->state = STATE_MENU;
	            strcpy(ctx->diagnostic_info, "AUTHENTICATED.");
	            Protocol_DisplayMenu();
	        }
	        else
	        {
	            char failMsg[] = "\r\nINVALID PASSWORD!\r\n";
	            HAL_UART_Transmit(&huart2, (uint8_t*)failMsg, strlen(failMsg), 100);
	            strcpy(ctx->diagnostic_info, "AUTHENTICATION FAILED.");
	        }
	        return;
	    }

	    // If a command is running, only allow cancellation.
	    if (ctx->state == STATE_RUNNING)
	    {
	        if (strlen(command) == 1 && (command[0] == 'B' || command[0] == 'b'))
	        {
	            ctx->cancelRequested = 1;
	            char cancelReq[] = "\r\nCANCELLATION REQUESTED.\r\n";
	            HAL_UART_Transmit(&huart2, (uint8_t*)cancelReq, strlen(cancelReq), 100);
	        }
	        return;
	    }

    // If in MENU state and the command is a single digit, process it
    if (ctx->state == STATE_MENU && strlen(command) == 1)
    {
        switch(command[0])
        {
            case '1':
            {
                char prompt[] = "\r\nENTER SERVO COMMAND IN FORMAT: ANGLE,STEP,CHECKSUM\r\n";
                HAL_UART_Transmit(&huart2, (uint8_t*)prompt, strlen(prompt), 100);
                ctx->state = STATE_WAIT_SERVO;
                return;
            }
            case '2':
            {
                Protocol_SetServoAngle(ctx, 90);
                char shutMsg[] = "\r\nMOTOR SHUTDOWN: SERVO SET TO 90.\r\n";
                HAL_UART_Transmit(&huart2, (uint8_t*)shutMsg, strlen(shutMsg), 100);
                Protocol_DisplayMenu();
                return;
            }
            case '3':
            {
                char statMsg[150];
                sprintf(statMsg, "\r\nSTATUS: ANGLE=%d, DIAG=%s\r\n",
                        ctx->current_servo_angle, ctx->diagnostic_info);
                HAL_UART_Transmit(&huart2, (uint8_t*)statMsg, strlen(statMsg), 100);
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
                char unknown[] = "\r\nUNKNOWN MENU OPTION.\r\n";
                HAL_UART_Transmit(&huart2, (uint8_t*)unknown, strlen(unknown), 100);
                Protocol_DisplayMenu();
                return;
            }
        }
    }

    // If in WAIT_SERVO, parse numeric command: angle,step,checksum
       if (ctx->state == STATE_WAIT_SERVO)
       {
           // Remove parentheses if user typed them
           if (command[0] == '(' && command[strlen(command)-1] == ')')
           {
               command[strlen(command)-1] = '\0';
               command++;
           }

           // Split by commas
           char *field1 = strtok(command, ",");
           char *field2 = strtok(NULL, ",");
           char *field3 = strtok(NULL, ",");

           if (!field1 || !field2 || !field3)
           {
               char err[] = "\r\nFORMAT ERROR: MUST BE ANGLE,STEP,CHECKSUM\r\n";
               HAL_UART_Transmit(&huart2, (uint8_t*)err, strlen(err), 100);
               ctx->state = STATE_MENU;
               Protocol_DisplayMenu();
               return;
           }

           int angle = atoi(field1);
           int step  = atoi(field2);
           int userCksum = atoi(field3);

           // Compute the expected checksum as a simple addition
           uint8_t compCksum = ComputeChecksumFromNumbers(angle, step);

           // Debug: show parse results
           char dbg[80];
           sprintf(dbg, "\r\nCOMMAND RECEIVED: %d,%d,%d => COMP=%d\r\n", angle, step, userCksum, compCksum);
           HAL_UART_Transmit(&huart2, (uint8_t*)dbg, strlen(dbg), 100);

           if (userCksum != compCksum)
           {
               char cke[] = "\r\nCHECKSUM ERROR.\r\n";
               HAL_UART_Transmit(&huart2, (uint8_t*)cke, strlen(cke), 100);
               ctx->state = STATE_MENU;
               Protocol_DisplayMenu();
               return;
           }

           // Clamp the target angle if necessary.
           if (angle > 165)
               angle = 165;

           // Instead of running the ramp immediately (in interrupt context),
           // store the command and set the pending flag.
           ctx->pendingTargetAngle = (uint8_t)angle;
           ctx->pendingStep = (uint8_t)step;
           ctx->commandPending = 1;

           char queuedMsg[] = "\r\nCOMMAND QUEUED. EXECUTING...\r\n";
           HAL_UART_Transmit(&huart2, (uint8_t*)queuedMsg, strlen(queuedMsg), 100);
           return;
       }

    // Otherwise, fallback
    Protocol_DisplayMenu();
}
