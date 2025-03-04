#ifndef PROTOCOL_H
#define PROTOCOL_H

#include "main.h"
#include <stdint.h>

// Define protocol states.
typedef enum {
    STATE_MENU,       // Waiting for a menu selection.
    STATE_WAIT_SERVO, // Waiting for the servo command (numeric format: angle,step,checksum).
    STATE_RUNNING     // Command execution (ramping in progress).
} ProtocolState;

// Protocol context structure.
typedef struct
{
    uint8_t authenticated;        // 0 = locked, 1 = unlocked.
    uint8_t current_servo_angle;  // Current servo angle (effective range 0–165).
    ProtocolState state;          // Current state.
    uint8_t cancelRequested;      // Flag to cancel a running operation.
    char diagnostic_info[100];    // Diagnostic message.

    // New fields for queuing a servo command.
    uint8_t pendingTargetAngle;
    uint8_t pendingStep;
    uint8_t commandPending;       // 1 if a servo command is waiting to be executed.
} ProtocolContext;


// Initialize the protocol context.
void Protocol_Init(ProtocolContext *ctx);

// Process a complete command line received from UART.
// - If not authenticated, treat the command as a password attempt.
// - In MENU state, expect a single-digit selection.
// - In WAIT_SERVO state, expect a servo command in the format: angle,step,checksum
// - In RUNNING state, only a cancellation command ("B") is processed.
void Protocol_ProcessCommand(ProtocolContext *ctx, char *command);

// Set the servo angle (with clamping to 165 and no-change detection) and update PWM output.
uint8_t Protocol_SetServoAngle(ProtocolContext *ctx, uint8_t angle);

// Run a motor command by ramping from the current angle to the target using the given step.
// Checks for cancellation.
void Protocol_RunCommand(ProtocolContext *ctx, uint8_t targetAngle, uint8_t step);

// Display the main menu (in uppercase).
void Protocol_DisplayMenu(void);

// Display detailed help information (in uppercase).
void Protocol_DisplayHelp(void);

// Compute checksum as (angle + step) modulo 256.
uint8_t ComputeChecksumFromNumbers(int angle, int step);

#endif // PROTOCOL_H
