/* AutoFuzz self-test: functions under test (see ../autofuzz.yaml). */
#ifndef SELFTEST_H
#define SELFTEST_H

int  add_small(int a, int b);
int  wait_ready(int tries);
int  has_name(void);
void led_on(void);
void cpu_nop(void);
void run_forever(void);

#endif
