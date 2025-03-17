#ifndef SERVO_DEFS_H
#define SERVO_DEFS_H

// Servo angle limits
#define SERVO_MIN_ANGLE         0
#define SERVO_MAX_ANGLE         165
#define SERVO_DEFAULT_ANGLE     0

// PWM pulse values corresponding to servo positions
#define SERVO_MIN_PULSE         500
#define SERVO_MAX_PULSE         2500
#define SERVO_PULSE_RANGE       (SERVO_MAX_PULSE - SERVO_MIN_PULSE)

// Delay between ramp steps (milliseconds)
#define SERVO_RAMP_DELAY_MS     100

#endif // SERVO_DEFS_H
