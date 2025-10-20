# AutoFuzz: Automated Testing for Embedded C

**Multi-layer testing framework** that generates unit tests, edge-case tests, and fuzz harnesses automatically. Found 2 critical security bugs (buffer overflow + integer overflow) in STM32 firmware.

---

## What It Does

AutoFuzz analyzes your C code and automatically generates:
1. **Edge tests** - Boundary values (INT_MAX, INT_MIN, buffer limits)
2. **Fuzz harnesses** - LibFuzzer tests for random input exploration
3. Runs **Millions of test cases**

---

## Quick Start

### Prerequisites
```bash
# Ubuntu/Debian
sudo apt-get install build-essential clang libfuzzer-12-dev libcmocka-dev python3

# macOS
brew install llvm cmocka python3
```

### Run Tests
```bash
cd Tests/unit_tests
make test          # Run everything (~3 min)
make unit          # Manual unit tests only
make edge          # Auto-generated edge tests
make fuzz          # Fuzzing (60s per function)
```

---

## How To Integrate AutoFuzz Into Your Project

### Step 1: Copy the Framework
```bash
your_project/
├── tests/                         # Create this
│   ├── autofuzz/                 # Copy from Tests/unit_tests/autofuzz/
│   │   ├── scanner.py
│   │   ├── generator.py
│   │   ├── config.py             # ← YOU EDIT THIS
│   │   ├── main.py
│   │   └── autofuzz_rt.h
│   ├── Makefile                  # Copy and modify
│   └── test_common.c/h           # Your test utilities
```

### Step 2: Configure for Your Domain

Edit `autofuzz/config.py` with your system's critical values:
```python
# File: autofuzz/config.py

# CRITICAL: Add your buffer sizes
STRING_SEEDS = [
    # Your protocol commands
    '"START"',
    '"STOP"',
    '"STATUS"',
    
    # Your buffer boundaries (MOST IMPORTANT!)
    '"' + 'A' * 255 + '"',   # UART_BUFFER_SIZE - 1
    '"' + 'A' * 256 + '"',   # Exactly UART_BUFFER_SIZE ← Test this!
    '"' + 'A' * 257 + '"',   # One over
    '"' + 'A' * 1024 + '"',  # DMA_BUFFER_SIZE
    
    # Edge cases
    '""',                     # Empty
    '"\\x00"',               # Null byte
    '"\\r\\n"',              # CRLF
]

# Add your system's constants
GENERIC_EDGES = {
    "char *": STRING_SEEDS,
    "int": mk_int_edges(32, True),
    # ... other types
}
```

**Key Point:** The buffer overflow was found because we tested at **exactly 1024 bytes** (the actual buffer size). Generic values like 100 bytes missed it.

### Step 3: Point to Your Code

Edit the `Makefile`:
```makefile
# Point to your source files
SRC_DIR = ../../src                    # Your source code
INCLUDES = -I$(SRC_DIR)/include        # Your headers

# List your source files to test
SRCS = $(SRC_DIR)/protocol.c \
       $(SRC_DIR)/parser.c \
       $(SRC_DIR)/utils.c

# Build object files
TEST_COMMON_OBJ = build/test_common.o $(SRCS:.c=.o)
```

### Step 4: Generate Tests
```bash
make build         # Triggers autofuzz code generation
```

This creates:
- `deterministic_edge_*.c` - Tests with boundary values
- `random_fuzz_*.c` - LibFuzzer harnesses

### Step 5: Run Tests
```bash
make test          # Everything
make edge          # Just edge tests
make fuzz          # Just fuzzing
```

---

## What to Edit: File-by-File Guide

###  `autofuzz/config.py` - **YOU MUST EDIT THIS**

**Purpose:** Define domain-specific test values

**What to change:**
```python
# 1. Add your protocol commands
STRING_SEEDS = [
    '"YOUR_COMMAND_1"',
    '"YOUR_COMMAND_2"',
]

# 2. Add your buffer sizes (CRITICAL!)
# Look for #define BUFFER_SIZE in your code
STRING_SEEDS += [
    '"' + 'A' * YOUR_BUFFER_SIZE + '"',      # Exact size
    '"' + 'A' * (YOUR_BUFFER_SIZE-1) + '"',  # One less
    '"' + 'A' * (YOUR_BUFFER_SIZE+1) + '"',  # One more
]

# 3. Add your numeric ranges
# If you have angle limits 0-180:
INT_EDGES = [-1, 0, 1, 179, 180, 181, 255]

# 4. Adjust fuzzing parameters
FZ_MAX_LEN = 4096              # Max input size for fuzzer
EDGE_CAP = 12                  # How many edge values per parameter
```

**Example from this project:**
```python
STRING_SEEDS = [
    '"UNLOCK"',                 # Authentication password
    '"(90,5,95)"',             # Valid servo command
    '"' + 'A' * 1024 + '"',    # DMA_BUFFER_SIZE ← Found the bug!
]
```

---

###  `Makefile` - **EDIT PATHS ONLY**

**What to change:**
```makefile
# Line ~10: Point to your source code
SRC_DIR = ../../Core/Src          # Change this
INCLUDES = -I../../Core/Inc       # Change this

# Line ~20: List files to test
SRCS = $(SRC_DIR)/protocol.c \
       $(SRC_DIR)/myfile.c        # Add your files

# Line ~100: Optional - adjust fuzzing time
FUZZ_MAX_SECS ?= 60               # Seconds per function
```

**Don't change:** Compiler flags, sanitizer settings, test targets

---

###  `test_common.c/h` - **YOUR TEST UTILITIES**

**Purpose:** Mocks, stubs, helper functions

**Example:**
```c
// test_common.c
void mock_HAL_UART_Transmit(char *data, size_t len) {
    // Mock UART for testing
}

void reset_system_state(void) {
    // Reset global state between tests
}
```

---

###  Manual Unit Tests (Optional)

Create `test_myfeature.c` for business logic tests:
```c
#include <cmocka.h>
#include "test_common.h"

static void test_authentication(void **state) {
    assert_true(authenticate("valid_password"));
    assert_false(authenticate("wrong_password"));
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_authentication),
    };
    return cmocka_run_group_tests(tests, NULL, NULL);
}
```

Add to Makefile:
```makefile
MANUAL_TESTS += test_myfeature.elf
```

---

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/autofuzz.yml`:
```yaml
name: AutoFuzz Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Install Dependencies
      run: |
        sudo apt-get update
        sudo apt-get install -y clang libfuzzer-12-dev libcmocka-dev python3
    
    - name: Run AutoFuzz Tests
      run: |
        cd Tests/unit_tests
        make test
      timeout-minutes: 5
    
    - name: Upload Crash Reports
      if: failure()
      uses: actions/upload-artifact@v3
      with:
        name: crashes
        path: Tests/unit_tests/crashes/
```

**What this does:**
1. **Triggers:** Runs on every push/PR
2. **Install:** Sets up clang, fuzzer, test framework
3. **Test:** Runs all tests (unit + edge + fuzz)
4. **Timeout:** Fails if tests hang (5 min limit)
5. **Upload crashes:** Saves crash files if bugs found

**Customize:**
```yaml
# Run longer fuzzing on main branch
- name: Extended Fuzzing (main branch only)
  if: github.ref == 'refs/heads/main'
  run: |
    cd Tests/unit_tests
    make fuzz FUZZ_MAX_SECS=300  # 5 minutes per function
```

---

### GitLab CI

Create `.gitlab-ci.yml`:
```yaml
stages:
  - test

autofuzz:
  stage: test
  image: ubuntu:22.04
  
  before_script:
    - apt-get update
    - apt-get install -y clang libfuzzer-12-dev libcmocka-dev python3 make
  
  script:
    - cd Tests/unit_tests
    - make test
  
  artifacts:
    when: on_failure
    paths:
      - Tests/unit_tests/crashes/
    expire_in: 30 days
  
  timeout: 5 minutes
```

---

## Understanding Test Output

### Success (No Bugs)
```
=== EDGE: deterministic_edge_Protocol_ProcessCommand ===
[ RUN      ] test_Protocol_ProcessCommand_edge_1
[       OK ] test_Protocol_ProcessCommand_edge_1
...
[  PASSED  ] 12 test(s).
```

### Failure (Bug Found)
```
=== EDGE: deterministic_edge_Protocol_ProcessCommand ===
[ RUN      ] test_Protocol_ProcessCommand_edge_3
AddressSanitizer: stack-buffer-overflow
READ of size 1026 at 0x7ffc...
    #0 in strtok
    #1 in handle_servo_cmd test_common.c:80
    
SUMMARY: AddressSanitizer: stack-buffer-overflow
```

**What to do:**
1. Note the function and line number
2. Check `crashes/` directory for reproduction input
3. Run: `./deterministic_edge_Protocol_ProcessCommand` to reproduce
4. Fix the bug
5. Re-run tests to verify fix

---

## How It Works Internally
```
1. Scanner (scanner.py)
   ↓
   Extracts function signatures from object files
   Example: void Protocol_ProcessCommand(ProtocolContext*, char*)
   
2. Generator (generator.py)
   ↓
   Creates test harnesses:
   - deterministic_edge_*.c (boundary values)
   - random_fuzz_*.c (LibFuzzer harnesses)
   
3. Makefile
   ↓
   Compiles with AddressSanitizer/UBSan
   Runs tests
   Reports crashes
```

**Key Technologies:**
- **LibFuzzer:** Coverage-guided fuzzing engine
- **AddressSanitizer:** Detects buffer overflows, use-after-free
- **UndefinedBehaviorSanitizer:** Catches integer overflow, null pointer deref
- **CMocka:** Unit test framework

---

## Limitations & Future Work

### Current Limitations
1. **Only tests global functions** - Static functions are invisible
2. **Requires manual buffer size config** - Can't auto-detect `#define BUFFER_SIZE`
3. **No state sequences** - Tests functions individually, not call chains

### Planned Improvements
1. Parse source code directly (using libclang) to find static functions
2. Extract buffer sizes from `#define` statements automatically
3. Add stateful fuzzing for multi-step protocol testing

---

## Troubleshooting

### "No functions found"
- Check `SRC_DIR` path in Makefile
- Ensure files are compiled: `make build`
- Run: `nm build/*.o` to see available symbols

### "Fuzzer not found"
```bash
# Ubuntu
sudo apt-get install libfuzzer-12-dev

# macOS
brew install llvm
export PATH="/usr/local/opt/llvm/bin:$PATH"
```

### Tests run but find nothing
- **Check config.py** - Are you testing actual buffer sizes?
- Increase fuzzing time: `make fuzz FUZZ_MAX_SECS=300`
- Add domain-specific test values to STRING_SEEDS

### Crashes not preserved
- Don't run `make clean` between fuzzing sessions
- Crashes are in `crashes/` - version control this directory
- Replay: `./random_fuzz_FUNCTION crashes/crash-*`

---

## Project Structure
```
ServoProject/
├── Core/                          # Your embedded firmware
│   ├── Src/
│   │   ├── protocol.c            # Code under test
│   │   └── servo.c
│   └── Inc/
│
├── Tests/unit_tests/              # AutoFuzz framework
│   ├── autofuzz/                 # Core framework
│   │   ├── scanner.py            # Extract function signatures
│   │   ├── generator.py          # Generate test code
│   │   ├── config.py             # ← EDIT: Your test values
│   │   ├── main.py               # Orchestration
│   │   └── autofuzz_rt.h         # Runtime helpers
│   │
│   ├── Makefile                  # ← EDIT: Paths to your code
│   ├── test_common.c/h           # ← EDIT: Your mocks/stubs
│   │
│   ├── test_*.c                  # Manual unit tests (optional)
│   ├── deterministic_edge_*.c    # Auto-generated (don't edit)
│   ├── random_fuzz_*.c           # Auto-generated (don't edit)
│   │
│   ├── crashes/                  # Bug reproductions (version control!)
│   └── lf_corpus/                # Evolved test corpus (ignore)
│
└── .github/workflows/
    └── autofuzz.yml              # CI/CD configuration
```


## License

MIT License

---

## Summary: 3 Steps to Get Started

1. **Copy `autofuzz/` to your project**
2. **Edit `config.py`** - Add your buffer sizes and protocol commands
3. **Edit `Makefile`** - Point to your source files
4. Run `make test`

---

**Questions?** Open an issue or check the generated test code to understand what's being tested.
