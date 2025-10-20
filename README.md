# AutoFuzz: Embedded Systems Testing Framework

**Automated multi-layer testing for embedded C** - Combines unit tests, edge-case generation, and coverage-guided fuzzing. Found 2 critical security vulnerabilities in STM32 servo controller firmware.

## Critical Bugs Found

- **Stack Buffer Overflow** (CRITICAL) - Exploitable memory corruption in protocol parser
- **Signed Integer Overflow** (HIGH) - Undefined behavior in checksum function
- **4 Logic Bugs** (MEDIUM) - Input validation and state machine issues

**Total: 6 bugs detected, 200M+ test executions in <3 minutes**

---

## Quick Start
```bash
# Install dependencies (Ubuntu)
sudo apt-get install build-essential clang libfuzzer-12-dev libcmocka-dev python3

# Run tests
cd Tests/unit_tests
make test          # All tests (~3 min)
make unit          # Unit tests only
make edge          # Edge tests only
make fuzz          # Fuzzing (60s/function)
```

---

## Project Structure
```
ServoProject/
├── Core/                          # STM32 firmware
│   ├── Src/
│   │   ├── protocol.c            # ⚠️ Buffer overflow found here
│   │   └── servo.c
│   └── Inc/
├── Tests/unit_tests/
│   ├── autofuzz/                 # Test generator framework
│   │   ├── scanner.py            # Extract function signatures
│   │   ├── generator.py          # Generate test harnesses
│   │   └── config.py             # Domain-specific test values
│   ├── test_*.c                  # Manual unit tests
│   ├── deterministic_edge_*.c    # Auto-generated edge tests
│   ├── random_fuzz_*.c           # Auto-generated fuzz harnesses
│   ├── crashes/                  # Discovered bugs (version controlled)
│   └── Makefile
└── Drivers/                      # STM32 HAL
```

---

## Testing Results

| Test Type | Tests | Bugs Found | Time |
|-----------|-------|------------|------|
| Unit Tests | 22 | 4 logic bugs | <5s |
| Edge Tests | 51 | 2 critical | <10s |
| Fuzz Tests | 200M iterations | 2 critical | 3m |

### Bug Breakdown
- 🔴 CRITICAL (2): Memory safety, exploitable
- 🟠 HIGH (1): Undefined behavior
- 🟡 MEDIUM (4): Logic errors

---

## Critical Bug #1: Stack Buffer Overflow

**File:** `Core/Src/protocol.c:78`  
**Severity:** CRITICAL - Exploitable RCE
```c
// VULNERABLE CODE
char buf[1024];
for (i = 0; i < sizeof(buf); ++i) {
    if (cmd_raw[i] == '\0') break;
    buf[i] = cmd_raw[i];
}
if (i < sizeof(buf)) buf[i] = '\0';  // ← BUG: Never runs if i==1024

// Later: strtok() reads past buffer → CRASH
```

**How Found:**
- Edge test: Input of exactly 1024 bytes → immediate crash
- Fuzzer: Found with 1983-byte input after 860k iterations
- AddressSanitizer: `stack-buffer-overflow at offset 1056`

**Fix:**
```c
buf[sizeof(buf)-1] = '\0';  // Always null-terminate
```

---

## Critical Bug #2: Signed Integer Overflow

**File:** `Tests/unit_tests/test_common.c:162`  
**Severity:** HIGH - Undefined behavior
```c
// VULNERABLE CODE
uint8_t ComputeChecksumFromNumbers(int a, int b) {
    return (uint8_t)(a + b);  // ← UB on INT_MAX + INT_MAX
}
```

**How Found:**
- Edge test #1: `ComputeChecksum(INT_MIN, INT_MIN)` → UBSan abort
- Fuzzer: Detected in <1 second

**Fix:**
```c
return (uint8_t)((unsigned int)a + (unsigned int)b);
```

---

## Architecture: Three-Layer Testing

### 1. Unit Tests - Business Logic
```c
assert(Protocol_Authenticate(&ctx, "UNLOCK") == 1);  // Valid
assert(Protocol_Authenticate(&ctx, "WRONG") == 0);   // Invalid
```
**Finds:** Expected behavior violations

### 2. Edge Tests - Boundary Conditions
```c
test_Protocol_ProcessCommand("A" * 1024);  // Buffer boundary
test_ComputeChecksum(INT_MAX, INT_MAX);    // Type limits
```
**Finds:** Off-by-one, overflows

### 3. Fuzz Tests - Random Exploration
```c
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    Protocol_ProcessCommand(&ctx, (char*)data);
    return 0;
}
```
**Finds:** Unexpected inputs, memory corruption

---

## Configuration

Domain-specific test values in `autofuzz/config.py`:
```python
STRING_SEEDS = [
    '"(90,5,95)"',          # Valid servo command
    '"' + 'A' * 1024 + '"', # DMA_BUFFER_SIZE ← Found the bug!
    '"UNLOCK"',             # Auth password
]
```

**Key Lesson:** Testing at actual buffer sizes (1024 bytes) caught the bug. Generic values (100 bytes) missed it.

---

## CI/CD Integration
```yaml
# .github/workflows/tests.yml
- name: AutoFuzz Tests
  run: |
    cd Tests/unit_tests
    make test
```

**Runtime:** <3 minutes → suitable for every commit

---

## Performance Metrics

| Function | Iterations/sec | Result |
|----------|----------------|--------|
| `HAL_Delay` | 450k | 27M tests, 0 bugs |
| `Protocol_ProcessCommand` | 290k | Crash at 860k iterations |
| `ComputeChecksum` | N/A | Immediate crash |

**Throughput:** ~200M test executions in 3 minutes

---

## Future Work

### Critical Improvements
1. **Static function parsing** - Currently only tests global functions
2. **Auto-detect buffer sizes** - Manual config required for `DMA_BUFFER_SIZE`
3. **Stateful fuzzing** - Test function call sequences, not single calls

### Integration
4. **Corpus persistence** - Preserve evolved test cases between runs
5. **Continuous fuzzing** - OSS-Fuzz integration for 24/7 testing
6. **Coverage reports** - HTML visualization of tested code

---

## What Makes This Work

✅ **AddressSanitizer/UBSan** - All bugs found via runtime sanitizers  
✅ **Domain knowledge** - Configured with protocol-specific test values  
✅ **Multi-layer coverage** - Each method finds different bug classes  
✅ **CI-friendly** - 3 minutes total, zero false positives

---

## Requirements

- clang with libFuzzer
- CMocka (unit testing)
- Python 3
- AddressSanitizer/UndefinedBehaviorSanitizer

---

## License

MIT License

---

## Security Note

This repo contains proof-of-concept exploits for educational purposes. Vulnerabilities are fixed in current code.

---

**AutoFuzz: Proving automated testing catches bugs humans miss** 🔍
```

---

# GitHub Repository Description (280 chars max)
```
Automated testing framework for embedded C systems. Combines unit tests, edge-case generation, and LibFuzzer to find security bugs. Found 2 critical vulnerabilities (buffer overflow + integer overflow) in STM32 firmware. 200M tests in 3 minutes.
```

---

# GitHub Topics/Tags
```
embedded-systems
fuzzing
testing
security
stm32
libfuzzer
address-sanitizer
unit-testing
c
firmware
automation
ci-cd
buffer-overflow
embedded-security