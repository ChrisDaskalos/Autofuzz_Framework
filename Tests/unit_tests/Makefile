CC      = gcc
CFLAGS  = -Wall -Wextra -g -std=c11 -DUNIT_TEST -I../../Core/Inc -I.
LDFLAGS = -lcmocka

# List of test sources
TEST_SRC = \
  test_protocol_checksum.c \
  test_protocol_authentication.c \
  test_protocol_init.c \
  test_protocol_menu.c \
  test_protocol_servo_command.c \
  test_protocol_state_machine.c

# Our project sources we want to test
PROJECT_SRC = \
  ../../Core/Src/protocol.c \
  ../../Core/Src/servo.c

# The file that "defines" the stubs
STUBS_SRC = test_common.c

# Each .c in TEST_SRC becomes a separate .elf
TEST_ELF = $(TEST_SRC:.c=.elf)

.PHONY: all clean
all: $(TEST_ELF)

# We also rebuild if test_common.h changes
$(TEST_ELF): test_common.h

# Each test .elf is built from:
# 1) The single test .c file
# 2) The project sources
# 3) The stubs definitions (test_common.c)
%.elf: %.c $(PROJECT_SRC) $(STUBS_SRC)
	$(CC) $(CFLAGS) -o $@ $(PROJECT_SRC) $(STUBS_SRC) $< $(LDFLAGS)

clean:
	rm -f *.elf
