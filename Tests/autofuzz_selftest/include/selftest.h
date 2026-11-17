/* AutoFuzz self-test: functions under test (see ../autofuzz.yaml). */
#ifndef SELFTEST_H
#define SELFTEST_H

int  add_small(int a, int b);
int  wait_ready(int tries);
int  has_name(void);
int  first_item(const int *items);
int  ratio(int a, int b);
void led_on(void);
void cpu_nop(void);
void run_forever(void);

#endif
