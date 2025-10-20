# File: autofuzz/config.py
"""
Configuration and global constants for the AutoFuzz harness generator.
CORRECTED VERSION - Fixes type matching and adds protocol-specific seeds
"""
import os
import pathlib
from typing import Final, List, Union, Dict

# ---------------------------------------------------------------------------
# Environment-driven parameters
# ---------------------------------------------------------------------------
EDGE_CAP: Final[int] = int(os.getenv("EDGE_CAP", "12"))  # ← FIXED: Reasonable default
ROOT: Final[pathlib.Path] = pathlib.Path(__file__).resolve().parents[1]
GEN_DIR: Final[pathlib.Path] = ROOT
STUB_SOURCES: Final[List[str]] = os.environ.get("STUB_SRCS", "").split()

# Optional fuzz tunables the generator may honor
FZ_MAX_LEN: Final[int] = int(os.getenv("FZ_MAX_LEN", "4096"))  # ← FIXED: More reasonable
FZ_RSS_LIMIT_MB: Final[int] = int(os.getenv("FZ_RSS_LIMIT_MB", "600"))

# ---------------------------------------------------------------------------
# Edge-value generators
# ---------------------------------------------------------------------------
def mk_int_edges(bit_width: int, signed: bool) -> List[int]:
    """Canonical edges for an integer type."""
    lo = -(1 << (bit_width - 1)) if signed else 0
    hi = (1 << (bit_width - 1)) - 1 if signed else (1 << bit_width) - 1
    extras = {2, -2}
    if bit_width >= 16:
        extras |= {0x7FFF, 0x8000, -0x8000, 0xFFFF}
    if bit_width >= 32:
        extras |= {0x7FFFFFFF, 0x80000000, -0x80000000, 0xFFFFFFFF}
    core = [lo, lo + 1, -1, 0, 1, 2, hi - 1, hi] + [e for e in extras]
    return [v for v in sorted(set(core)) if lo <= v <= hi]

# ---------------------------------------------------------------------------
# FIXED: Enhanced string seeds with protocol-specific values
# ---------------------------------------------------------------------------
STRING_SEEDS: Final[List[str]] = [
    # Basic edge cases
    '""',                    # Empty string
    '" "',                   # Single space
    '"  "',                  # Multiple spaces
    '"\\t"',                 # Tab
    '"\\r\\n"',              # CRLF
    '"\\n"',                 # LF
    
    # Protocol commands - AUTHENTICATION
    '"1234"',              # ← ADDED: Valid password
    '"unlock"',              # ← ADDED: Wrong case
    '"WRONG"',               # ← ADDED: Invalid password
    '"LOCK"',                # ← ADDED: Similar but wrong
    
    # Protocol commands - MENU OPTIONS
    '"1"',                   # Menu option 1 (start servo)
    '"2"',                   # Menu option 2 (shutdown)
    '"3"',                   # Menu option 3 (status)
    '"4"',                   # Menu option 4 (help)
    '"0"',                   # Before menu range
    '"5"',                   # After menu range
    '"9"',                   # Way out of range
    
    # Protocol commands - CANCEL
    '"B"',                   # ← ADDED: Cancel (uppercase)
    '"b"',                   # ← ADDED: Cancel (lowercase)
    '"C"',                   # Wrong cancel letter
    
    # Servo commands - VALID
    '"(90,5,95)"',           # ← ADDED: Valid (angle=90, step=5, checksum=95)
    '"(0,1,1)"',             # ← ADDED: Minimum angle
    '"(180,5,185)"',         # ← ADDED: Maximum valid angle
    '"(100,10,110)"',        # ← ADDED: Another valid
    
    # Servo commands - EDGE CASES
    '"(181,5,186)"',         # ← ADDED: Angle just over max (181 > 180)
    '"(90,0,90)"',           # ← ADDED: Zero step
    '"(255,1,0)"',           # ← ADDED: Overflow checksum
    '"(180,255,179)"',       # ← ADDED: Large step
    '"(-1,1,0)"',            # ← ADDED: Negative angle
    
    # Servo commands - MALFORMED
    '"(90,5,99)"',           # ← ADDED: Wrong checksum
    '"(90,5)"',              # Missing checksum
    '"90,5,95"',             # Missing parentheses
    '"(90,5,95"',            # Missing closing paren
    '"90,5,95)"',            # Missing opening paren
    '"(,5,95)"',             # Missing angle
    '"(90,,95)"',            # Missing step
    '"(90,5,)"',             # Missing checksum
    '"()"',                  # Empty parens
    '"(,,)"',                # All commas
    '"(abc,def,ghi)"',       # ← ADDED: Non-numeric
    '"(  90  ,  5  ,  95  )"',  # Extra spaces
    
    # Buffer overflow attempts
    '"' + 'A' * 63 + '"',    # Just under buffer size
    '"' + 'A' * 64 + '"',    # Exactly buffer size
    '"' + 'A' * 65 + '"',    # Just over buffer size
    '"' + 'A' * 100 + '"',   # Way over buffer size
    # Buffer overflow attempts - DMA_BUFFER_SIZE BOUNDARIES (CRITICAL!)
    '"' + 'A' * 1022 + '"',   # ← ADD: Just under DMA_BUFFER_SIZE
    '"' + 'A' * 1023 + '"',   # ← ADD: One byte before DMA_BUFFER_SIZE
    '"' + 'A' * 1024 + '"',   # ← ADD: EXACTLY DMA_BUFFER_SIZE (triggers bug!)
    '"' + 'A' * 1025 + '"',   # ← ADD: One byte over DMA_BUFFER_SIZE
    '"' + 'A' * 2000 + '"',   # ← ADD: Way over DMA_BUFFER_SIZE
    '"' + 'A' * 4095 + '"',   # ← ADD: Maximum fuzzer length

    # With parentheses (servo command format)
    '"(' + 'A' * 1022 + ')"', # ← ADD: Valid format, at boundary
    '"(' + 'A' * 1024 + ')"', # ← ADD: Valid format, past boundary
    
    # Special characters
    '"\\x00"',               # Null byte
    '"\\x00\\x00"',          # Multiple nulls
    '"\\xff\\xff"',          # High bytes
    '"\\r"',                 # Carriage return
    '"\\n"',                 # Newline
    '"\\r\\n\\r\\n"',        # Multiple CRLFs
    
    # Edge numeric strings
    '"-1"',
    '"255"',
    '"256"',
    '"32767"',
    '"32768"',
    '"65535"',
    '"2147483647"',          # INT_MAX
    '"-2147483648"',         # INT_MIN
]

# ---------------------------------------------------------------------------
# FIXED: Mapping C types to generic edge-case values
# Added all common type variations to prevent lookup failures
# ---------------------------------------------------------------------------
GENERIC_EDGES: Final[Dict[str, List[Union[int, str]]]] = {
    # String types - ALL VARIATIONS
    "const char *": STRING_SEEDS,
    "char *": STRING_SEEDS,              # ← FIXED: Added non-const variant
    "char*": STRING_SEEDS,               # ← FIXED: Added no-space variant
    "const char*": STRING_SEEDS,         # ← FIXED: Added compact const variant
    
    # Integer types - 8-bit
    "uint8_t":   mk_int_edges(8, False),
    "int8_t":    mk_int_edges(8, True),
    "unsigned char": mk_int_edges(8, False),
    "signed char":   mk_int_edges(8, True),
    "char":      mk_int_edges(8, True),  # Assuming signed char
    
    # Integer types - 16-bit
    "uint16_t":  mk_int_edges(16, False),
    "int16_t":   mk_int_edges(16, True),
    "unsigned short": mk_int_edges(16, False),
    "short":     mk_int_edges(16, True),
    "short int": mk_int_edges(16, True),
    
    # Integer types - 32-bit (MOST IMPORTANT)
    "uint32_t":  mk_int_edges(32, False),
    "int32_t":   mk_int_edges(32, True),
    "int":       mk_int_edges(32, True),    # ← Already present
    "signed int": mk_int_edges(32, True),   # ← FIXED: Added variant
    "unsigned int": mk_int_edges(32, False),  # ← Already present
    "unsigned":  mk_int_edges(32, False),   # ← FIXED: Added short form
    
    # Integer types - 64-bit
    "uint64_t":  mk_int_edges(64, False),
    "int64_t":   mk_int_edges(64, True),
    "unsigned long":      mk_int_edges(64, False),
    "long":               mk_int_edges(64, True),
    "unsigned long long": mk_int_edges(64, False),
    "long long":          mk_int_edges(64, True),
    
    # Size types
    "size_t":    mk_int_edges(64, False),
    "ssize_t":   mk_int_edges(64, True),
    "ptrdiff_t": mk_int_edges(64, True),
    
    # Boolean types
    "bool":      [0, 1],
    "_Bool":     [0, 1],
}