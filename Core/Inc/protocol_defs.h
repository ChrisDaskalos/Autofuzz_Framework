#ifndef PROTOCOL_DEFS_H
#define PROTOCOL_DEFS_H

// Authentication
#define PROTOCOL_PASSWORD       "1234"

// Buffer sizes and timeouts
#define PROTOCOL_DIAG_SIZE      100
#define UART_TX_TIMEOUT         100
#define DMA_BUFFER_SIZE         1024

// Prompt and status messages 
#define WELCOME_MSG             "\r\nWELCOME. PLEASE ENTER PASSWORD:\r\n"
#define PASSWORD_ACCEPTED_MSG   "\r\nPASSWORD ACCEPTED!\r\n"
#define INVALID_PASSWORD_MSG    "\r\nINVALID PASSWORD!\r\n"

#define MENU_PROMPT             "\r\nMENU:\r\n" \
                                "1. SET SERVO ANGLE\r\n" \
                                "2. SHUTDOWN MOTOR\r\n" \
                                "3. DISPLAY STATUS\r\n" \
                                "4. HELP\r\n" \
                                "ENTER YOUR CHOICE: "

#define HELP_MESSAGE            "\r\n***** DETAILED HELP *****\r\n" \
                                "OPTION 1: SET SERVO ANGLE\r\n" \
                                "   ENTER A COMMAND IN THE FORMAT: ANGLE,STEP,CHECKSUM\r\n" \
                                "   ANGLE IN [0.." "165" "] (CLAMPED IF ABOVE 165)\r\n" \
                                "   STEP (E.G., 5)\r\n" \
                                "   CHECKSUM = ANGLE + STEP\r\n" \
                                "\r\n   EXAMPLE: 90,5,95\r\n" \
                                "OPTION 2: SHUTDOWN MOTOR\r\n" \
                                "   RESETS SERVO TO 90 DEGREES.\r\n" \
                                "OPTION 3: DISPLAY STATUS\r\n" \
                                "OPTION 4: HELP\r\n" \
                                "\r\nPRESS 'B' ANYTIME DURING A RAMP TO CANCEL AND RETURN TO MENU.\r\n" \
                                "******************************\r\n"

#define SERVO_CMD_PROMPT        "\r\nENTER SERVO COMMAND IN FORMAT: ANGLE,STEP,CHECKSUM\r\n"
#define CMD_QUEUED_MSG          "\r\nCOMMAND QUEUED. EXECUTING...\r\n"
#define CMD_EXECUTED_MSG        "\r\nCOMMAND EXECUTED. BACK TO MENU.\r\n"
#define MOTOR_SHUTDOWN_MSG      "\r\nMOTOR SHUTDOWN: SERVO SET TO 90.\r\n"
#define UNKNOWN_MENU_OPTION_MSG "\r\nUNKNOWN MENU OPTION.\r\n"
#define CHECKSUM_ERROR_MSG      "\r\nCHECKSUM ERROR.\r\n"
#define FORMAT_ERROR_MSG        "\r\nFORMAT ERROR: MUST BE ANGLE,STEP,CHECKSUM\r\n"
#define CANCEL_MSG              "\r\nCANCELING\r\n"

#endif // PROTOCOL_DEFS_H
