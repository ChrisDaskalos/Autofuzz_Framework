# File: autofuzz/config.py
"""
Configuration and global constants for the AutoFuzz harness generator.
"""
import os
import pathlib
from typing import Final, List, Union, Dict

# ---------------------------------------------------------------------------
# Environment-driven parameters
# ---------------------------------------------------------------------------

EDGE_CAP: Final[int] = int(os.getenv("EDGE_CAP", "65536"))
ROOT: Final[pathlib.Path] = pathlib.Path(__file__).resolve().parents[1]
GEN_DIR: Final[pathlib.Path] = ROOT
STUB_SOURCES: Final[List[str]] = os.environ.get("STUB_SRCS", "").split()

# Optional fuzz tunables the generator may honor
FZ_MAX_LEN: Final[int] = int(os.getenv("FZ_MAX_LEN", "4096"))
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
    core = [lo, lo + 1, -1, 0, 1, hi - 1, hi] + [e for e in extras]
    return [v for v in sorted(set(core)) if lo <= v <= hi]

# ---------------------------------------------------------------------------
# Default literal seeds for string parameters (helps parser paths)
# ---------------------------------------------------------------------------

STRING_SEEDS: Final[List[str]] = [
    '""', '" "', '"  "', '"\\t"', '"\\r\\n"',
    '"("', '")"', '","', '"-"',
    '"0"', '"1"', '"-1"', '"255"', '"32767"', '"2147483647"',
    '"servo"', '"SERVO"', '"cancel"', '"CANCEL"',
    '" servo"', '"cancel  "', '"  cancel  "',
    '"(90,2,92)"', '"(0,1,1)"', '"(180,5,185)"',
    '"(90,2,99)"', '"(180,0,180)"', '"(181,1,182)"',
    '"(400,1,401)"', '"(255,1,0)"', '"(foo,bar,baz)"',
    '"servo(90,2,92)"', '"servo( 90 , 2 , 92 )"',
    '"   cancel   "',
    '"\\x00\\x00"', '"\\xff\\xff"', '"\\x01\\x00"',
]

# ---------------------------------------------------------------------------
# Mapping C types to generic edge-case values
# ---------------------------------------------------------------------------

GENERIC_EDGES: Final[Dict[str, List[Union[int, str]]]] = {
    "uint8_t":   mk_int_edges(8, False)[:EDGE_CAP],
    "int8_t":    mk_int_edges(8, True )[:EDGE_CAP],
    "uint16_t":  mk_int_edges(16, False)[:EDGE_CAP],
    "int16_t":   mk_int_edges(16, True )[:EDGE_CAP],
    "uint32_t":  mk_int_edges(32, False)[:EDGE_CAP],
    "int32_t":   mk_int_edges(32, True )[:EDGE_CAP],
    "uint64_t":  mk_int_edges(64, False)[:EDGE_CAP],
    "int64_t":   mk_int_edges(64, True )[:EDGE_CAP],
    "size_t":    mk_int_edges(64, False)[:EDGE_CAP],
    "ssize_t":   mk_int_edges(64, True )[:EDGE_CAP],
    "int":             mk_int_edges(32, True )[:EDGE_CAP],   # ← added
    "unsigned int":    mk_int_edges(32, False)[:EDGE_CAP],   # ← added
    "const char *": STRING_SEEDS,
}


