#ifndef PROTOCOL_H
#define PROTOCOL_H



//#include "main.h"
#include <stdint.h>
#include "protocol_defs.h"

// Define protocol states.
typedef enum {
    STATE_MENU,
    STATE_WAIT_SERVO,
    STATE_RUNNING
} ProtocolState;

// Protocol context structure.
typedef struct
{
    uint8_t authenticated;
    uint8_t current_servo_angle;
    ProtocolState state;
    uint8_t cancelRequested;
    char diagnostic_info[PROTOCOL_DIAG_SIZE];

    // Fields for pending servo command.
    uint8_t pendingTargetAngle;
    uint8_t pendingStep;
    uint8_t commandPending;
} ProtocolContext;

// Declare the protocol context (defined only in protocol.c)
extern ProtocolContext protocol_ctx;

// Function prototypes.
void Protocol_Init(ProtocolContext *ctx);
void Protocol_ProcessCommand(ProtocolContext *ctx, char *command);
void Protocol_DisplayMenu(void);
void Protocol_DisplayHelp(void);
uint8_t ComputeChecksumFromNumbers(int angle, int step);

#endif // PROTOCOL_H
