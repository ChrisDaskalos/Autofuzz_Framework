#ifndef SERVO_DEFS_H
#define SERVO_DEFS_H

/* Absolute electrical limits of the servo*/
#define SERVO_MIN_PULSE     1000     /* µs */
#define SERVO_MAX_PULSE     3000    /* µs */
#define SERVO_PULSE_RANGE   (SERVO_MAX_PULSE - SERVO_MIN_PULSE)

/* Logical angle range you exposing to user */
#define SERVO_MAX_ANGLE     165     /* deg */
#define SERVO_DEFAULT_ANGLE 90

/* ─── NEW: largest step we will ever apply in one update ── */
#define SERVO_MAX_STEP      45      /* deg per update */
#define SERVO_RAMP_DELAY_MS 1000

#endif /* SERVO_DEFS_H */
