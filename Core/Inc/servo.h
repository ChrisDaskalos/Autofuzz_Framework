#ifndef SERVO_H
#define SERVO_H


//#include "main.h"
#include <stdint.h>
#include "servo_defs.h"

// Initialize servo hardware (if needed)
void Servo_Init(void);
void Servo_SetAngle(uint8_t angle);
void Servo_Ramp(uint8_t *currentAngle, uint8_t targetAngle, uint8_t step);

#endif // SERVO_H
