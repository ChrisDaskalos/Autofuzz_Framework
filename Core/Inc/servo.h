#ifndef SERVO_H
#define SERVO_H

#include "main.h"
#include <stdint.h>
#include "servo_defs.h"

// Initialize servo hardware (if needed)
void Servo_Init(void);

// Immediately set the servo angle (with clamping) and update PWM.
void Servo_SetAngle(uint8_t angle);

// Gradually ramp the servo from the current angle to the target angle.
void Servo_Ramp(uint8_t *currentAngle, uint8_t targetAngle, uint8_t step);

#endif // SERVO_H
