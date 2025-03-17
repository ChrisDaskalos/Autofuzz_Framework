# ServoProject – UART Protocol for MG90S Servo on STM32 Nucleo

This project implements a UART-based protocol for controlling an MG90S servo motor using an STM32 Nucleo F103RB board. The embedded firmware uses DMA-based UART reception with idle-line detection, a state machine for processing user commands (including authentication and menu selections), and PWM generation via TIM2 to control the servo.

The project is developed in STM32CubeIDE on Ubuntu and is structured to support both embedded builds (for the microcontroller) and host-based builds for unit testing on x86_64 using GCC and CMocka.

---

## Environment & Tools

### Embedded Environment
- **Hardware:** STM32 Nucleo F103RB board, MG90S servo motor
- **IDE/Toolchain:** STM32CubeIDE, `arm-none-eabi-gcc`, STM32 HAL (`stm32f1xx_hal`)
- **Firmware Features:** 
  - UART communication via DMA with idle-line detection
  - PWM-based servo control via TIM2
  - Interactive command protocol with a state machine (authentication, menu, servo command, ramping)

### Host (Unit Testing) Environment
- **Compiler:** GCC (x86_64)
- **Unit Testing Framework:** CMocka (using the `libcmocka-dev` package on Ubuntu)
- **Build System:** Makefile that rehosts embedded code as ELF executables for unit testing
- **Planned Enhancements:**
  - **Docker:** To run CMocka tests in containerized environments.
  - **LibFuzzer:** To integrate exhaustive randomized fuzz testing with finish conditions (e.g., time limits).

---

## Project Structure

```text
ServoProject/
├── Core/
│   ├── Inc/
│   │   ├── main.h
│   │   ├── protocol.h
│   │   ├── protocol_defs.h
│   │   ├── servo.h
│   │   └── servo_defs.h
│   └── Src/
│       ├── main.c
│       ├── protocol.c
│       ├── servo.c
│       └── (other source files)
├── Drivers/
│   └── (HAL driver files)
└── Tests/
    └── unit_tests/
        ├── test_common.h      (Host stubs and shared definitions)
        ├── test_common.c      (Global definitions for stubs)
        ├── test_protocol_checksum.c
        ├── test_protocol_authentication.c
        ├── test_protocol_init.c
        ├── test_protocol_menu.c
        ├── test_protocol_servo_command.c
        ├── test_protocol_state_machine.c
        └── Makefile           (Builds ELF executables for host-based testing)
```

---

## TODO

- **1. Differentiate 10 Functions for the UART Protocol (in a separate .c file) – DONE**  
  The embedded code has been refactored to isolate 10 key functions (if-then-else logic) for handling the UART protocol, parsing, state transitions, and command processing.

- **2. Build a Makefile Rule to Compile as .elf for x86_64 – DONE**  
  A host Makefile has been created in the `Tests/unit_tests/` folder to compile the embedded code (`protocol.c`, `servo.c`) into ELF executables for unit testing on x86_64.

- **3. Run CMocka Tests (on Docker Containers) for These Functions**  
  - **Objective:** Create Docker containers that build and run CMocka-based tests for the isolated functions.  
  - **Status:** Pending – Setup and integration of Docker with the unit test Makefile is next.

- **4. Extend the CMocka Code to Embed LibFuzzer Functionality (with Exhaustive-Random Testing and Finish Conditions)**  
  - **Objective:** Integrate LibFuzzer into the CMocka test harness to automatically generate random inputs and run until a finish condition (e.g., time limit) is met.  
  - **Status:** Pending – Research and implementation of LibFuzzer integration is next.

---

## How Unit Testing Helps Fix Embedded Code

- **Isolating Code Logic:**  
  Unit tests target individual functions or modules (e.g., command parsing, state transitions) independent of the hardware, allowing you to validate logic changes quickly.

- **Rapid Feedback & Regression Prevention:**  
  Automated tests provide immediate feedback, ensuring that any modifications don’t break existing behavior.

- **Documenting Expected Behavior:**  
  Unit tests serve as executable documentation. They show how functions are expected to behave under various conditions, including error scenarios.

- **Hardware Abstraction via Stubs:**  
  Stubs simulate the behavior of hardware-specific functions (such as UART and PWM calls), allowing you to test the logic without real hardware. While stubs do not simulate the entire behavior of the actual hardware, they let you verify that your software calls the HAL functions correctly.

- **Extended Testing with LibFuzzer (Planned):**  
  Future integration of LibFuzzer will allow exhaustive randomized testing to uncover edge cases and potential vulnerabilities in input parsing.

---

- **GDB Debugging:**  
  Run your test executables under GDB to obtain backtraces when a segfault or error occurs:
  ```bash
  gdb ./test_protocol_servo_command.elf  ..   
   into :(gdb) run
   into: (gdb) backtrace 
   OR ./test_protocol_xxx.elf (for Cmocka)
  ```

## Building and Running Tests via Docker

A **Dockerfile** is provided in the project root. It sets up an Ubuntu-based image, installs GCC, Make, libcmocka-dev, and GDB, then builds tests in `Tests/unit_tests/` and runs them automatically.

To build the Docker image (from the root of the project, where the Dockerfile is located):

```bash
docker build -t servo_project_tests .

docker run --rm servo_project_tests
```
The container will compile the code (via make) and then call run_tests.sh to run CMocka tests.


