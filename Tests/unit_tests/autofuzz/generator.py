# File: autofuzz/generator.py
"""
FINAL VERSION - Recognizes INT_MAX both as constant and literal value
"""
from pathlib import Path
from typing import Sequence, Set, List, Any, Dict
import re
import itertools

from .config import EDGE_CAP, STRING_SEEDS, GENERIC_EDGES, FZ_MAX_LEN

# ─────────────────────────────────────────────────────────────────────
# Type detection helpers
# ─────────────────────────────────────────────────────────────────────
_PROTOCTX_PTR = re.compile(r"\bProtocolContext\s*\*")

def _clean_type(pt: str) -> str:
    t = pt.replace("const", "").strip()
    t = " ".join(t.split())
    t = t.replace(" *", "*").replace("* ", "*")
    return t

def _canonical_key_for_generic(pt: str) -> str:
    """Map a parameter type to a key that likely exists in GENERIC_EDGES."""
    raw = pt.strip()
    t = _clean_type(raw)
    if t in GENERIC_EDGES:
        return t
    
    synonyms: Dict[str, str] = {
        "signed int": "int",
        "int32_t": "int32_t",
        "uint32_t": "uint32_t",
        "size_t": "size_t",
        "ssize_t": "ssize_t",
        "unsigned": "unsigned int",
        "unsigned int": "unsigned int",
        "long": "int64_t",
        "unsigned long": "uint64_t",
        "long long": "int64_t",
        "unsigned long long": "uint64_t",
        "char*": "const char *",
        "char *": "const char *",
    }
    
    if t in synonyms and synonyms[t] in GENERIC_EDGES:
        return synonyms[t]
    
    candidates = [raw, raw.replace("const", "").strip(), t.replace(" *", "*")]
    for c in candidates:
        if c in GENERIC_EDGES:
            return c
    
    return t

def _is_string(pt: str) -> bool:
    t = _clean_type(pt)
    t_nospace = t.replace(" ", "")
    return "char*" in t_nospace

def _is_pointer(pt: str) -> bool:
    return "*" in pt

def _is_signed32(pt: str) -> bool:
    t = _clean_type(pt)
    return t in ("int", "signed int", "int32_t")

def _is_integer_type(pt: str) -> bool:
    """Check if type is any integer type."""
    t = _clean_type(pt)
    int_types = {
        "int", "signed int", "unsigned int",
        "int8_t", "uint8_t", "int16_t", "uint16_t",
        "int32_t", "uint32_t", "int64_t", "uint64_t",
        "short", "long", "unsigned", "signed"
    }
    return t in int_types

def _needs_protocol_ctx(param_types: Sequence[str]) -> bool:
    return bool(param_types and _PROTOCTX_PTR.search(param_types[0]))

# ─────────────────────────────────────────────────────────────────────
# Token normalization helpers
# ─────────────────────────────────────────────────────────────────────
def _looks_c_string_literal(tok: str) -> bool:
    tok = tok.strip()
    return len(tok) >= 2 and tok[0] == '"' and tok[-1] == '"'

def _escape_c_string(s: str) -> str:
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

def _normalize_token(x: Any) -> str:
    if x is None:
        return "0"
    if isinstance(x, bool):
        return "1" if x else "0"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        return str(int(x)) if x.is_integer() else str(x)
    if isinstance(x, (bytes, bytearray)):
        try:
            return x.decode("utf-8", "ignore")
        except Exception:
            return "0"
    return str(x)

def _clamp_signed32(tok: str, raw: Any) -> str:
    t = tok.strip()
    if any(t.startswith(k) for k in ("INT_MAX", "INT_MIN")):
        return t
    try:
        if isinstance(raw, int):
            val = raw
            raw_txt = None
        else:
            val = int(t, 0)
            raw_txt = t
        if val > 2147483647:
            if raw_txt and "80000000" in raw_txt.lower():
                return "INT_MIN"
            return "INT_MAX"
        if val < -2147483648:
            return "INT_MIN"
        if val == 2147483648:
            return "INT_MIN"
        return str(val)
    except Exception:
        return t

# ─────────────────────────────────────────────────────────────────────
# Edge value generation
# ─────────────────────────────────────────────────────────────────────
def _lookup_generic_edges_for_type(pt: str) -> List[Any]:
    """Get edge values for a type from config."""
    if _is_string(pt):
        return STRING_SEEDS[:EDGE_CAP] if STRING_SEEDS else ['""']
    key = _canonical_key_for_generic(pt)
    vals = GENERIC_EDGES.get(key)
    if vals:
        return vals[:EDGE_CAP]
    if _is_pointer(pt):
        return ['NULL']
    return ['0', '1', '-1', 'INT_MAX', 'INT_MIN']

_NAMED_INTS = {
    "INT_MIN": -2**31, "INT_MAX": 2**31 - 1, "UINT_MAX": 2**32 - 1,
    "LONG_MIN": -2**63, "LONG_MAX": 2**63 - 1, "NULL": 0,
}

def _seed_sort_key(raw: Any):
    """Numbers (and INT_MAX etc.) first, by value; then text by length."""
    s = str(raw).strip()
    if s in _NAMED_INTS:
        return (0, _NAMED_INTS[s], s)
    try:
        return (0, int(s, 0), s)
    except ValueError:
        return (1, len(s), s)

def _ordered_seeds(seeds: Any) -> List[Any]:
    """
    Turn the scanner's *set* of seeds into a list with a fixed order.

    A Python set of strings has a different order in every run, and only
    the first EDGE_CAP seeds are used, so before this function every build
    tested a different random choice of seeds (sometimes with the long
    buffer-overflow strings, sometimes without).

    Now: sort (numbers by value, strings by length), and if there are more
    than EDGE_CAP, take EDGE_CAP values spread evenly from first to last.
    The smallest and largest values (e.g. the longest string) are always
    kept.
    """
    ordered = sorted(set(seeds), key=_seed_sort_key)
    n, k = len(ordered), EDGE_CAP
    if n <= k or k < 2:
        return ordered[:max(k, 0)] if n > k else ordered
    picks = sorted({round(j * (n - 1) / (k - 1)) for j in range(k)})
    return [ordered[p] for p in picks]

def _seed_list(pt: str, seeds: List[Any]) -> List[str]:
    """
    Turn a list of raw seeds into C tokens, ensuring extremes for integers.
    FIXED: Removes duplicates and guarantees INT_MIN/INT_MAX presence.
    """
    if not seeds:
        seeds = _lookup_generic_edges_for_type(pt)

    out: List[str] = []
    for raw in seeds[:EDGE_CAP]:
        tok = _normalize_token(raw)
        
        if _is_string(pt):
            out.append(tok if _looks_c_string_literal(tok) else _escape_c_string(tok))
            continue
        if _is_pointer(pt):
            out.append('NULL')
            continue
        if _is_signed32(pt):
            out.append(_clamp_signed32(tok, raw))
        else:
            out.append(tok)

    # *** FIX 1: Remove duplicates while preserving order ***
    seen = set()
    unique_out = []
    for val in out:
        if val not in seen:
            seen.add(val)
            unique_out.append(val)
    out = unique_out

    # *** FIX 2: For integer types, ensure INT_MIN and INT_MAX are present ***
    if _is_integer_type(pt) and out:
        has_int_max = any(v in ["2147483647", "INT_MAX"] for v in out)
        has_int_min = any(v in ["-2147483648", "INT_MIN"] for v in out)
        
        if not has_int_min:
            out.insert(0, "INT_MIN")
        if not has_int_max:
            out.append("INT_MAX")
        
        # Re-cap if we added values
        if len(out) > EDGE_CAP:
            middle_start = 1
            middle_end = EDGE_CAP - 1
            out = [out[0]] + out[middle_start:middle_end] + [out[-1]]

    return out or (['""'] if _is_string(pt) else (['NULL'] if _is_pointer(pt) else ['0']))

def _make_arg_decl(i: int, pt: str) -> str:
    """Generate variable declaration for a parameter."""
    if _is_string(pt):
        return f'{pt} a{i} = "";'
    if _is_pointer(pt):
        return f'{pt} a{i} = NULL;'
    return f'{pt} a{i} = ({pt})0;'

# ─────────────────────────────────────────────────────────────────────
# Smart test combination generation
# ─────────────────────────────────────────────────────────────────────
def _generate_test_combinations(seeds_per_param: List[List[str]], 
                                needs_ctx: bool,
                                max_tests: int = 12) -> List[List[str]]:
    """
    Generate smart combinations ensuring extremes are tested.
    CRITICAL FIX: Recognizes INT_MAX both as constant and literal value.
    """
    testable_seeds = []
    for i, seeds in enumerate(seeds_per_param):
        if needs_ctx and i == 0:
            continue
        if seeds:
            testable_seeds.append(seeds)
    
    if not testable_seeds:
        return [[]]
    
    if len(testable_seeds) == 1:
        # Single parameter: iterate through values
        return [[val] for val in testable_seeds[0][:max_tests]]
    
    if len(testable_seeds) == 2:
        # Remove duplicates from each parameter
        unique_seeds = []
        for seeds in testable_seeds:
            seen = set()
            unique = []
            for s in seeds:
                if s not in seen:
                    seen.add(s)
                    unique.append(s)
            unique_seeds.append(unique)
        
        combos_to_test = []
        
        # For each parameter, select 4 strategic values
        for param_idx, seeds in enumerate(unique_seeds):
            if len(seeds) <= 4:
                combos_to_test.append(seeds)
            else:
                # *** CRITICAL FIX: Guarantee both extremes are kept ***
                selected = []
                
                # MUST HAVE: minimum (first element)
                selected.append(seeds[0])
                
                # MUST HAVE: maximum (last element)
                selected.append(seeds[-1])
                
                # HIGHLY DESIRED: small positive value (for overflow testing)
                small_positive = None
                for s in seeds:
                    try:
                        if s in ["1", "2", "3"]:
                            small_positive = s
                            break
                        val = int(s) if (s.isdigit() or (s.startswith('-') and s[1:].isdigit())) else None
                        if val is not None and 1 <= val <= 10:
                            small_positive = s
                            break
                    except:
                        pass
                
                if small_positive and small_positive not in selected:
                    selected.append(small_positive)
                
                # Fill to 4 values: add near-minimum or middle value
                if len(selected) < 4:
                    for candidate in [seeds[1], "0", seeds[len(seeds)//2], seeds[-2]]:
                        if candidate in seeds and candidate not in selected:
                            selected.append(candidate)
                            if len(selected) >= 4:
                                break
                
                combos_to_test.append(selected)
        
        # Generate cartesian product
        all_combos = list(itertools.product(*combos_to_test))
        
        # *** CRITICAL FIX: Prioritize overflow-likely combinations ***
        def combo_priority(combo):
            """Lower score = higher priority. Prioritize overflow-inducing combos."""
            score = 0
            for val in combo:
                try:
                    v_str = val.replace("INT_MAX", "2147483647").replace("INT_MIN", "-2147483648")
                    v = int(v_str)
                    
                    # *** FIXED: Recognize INT_MAX/INT_MIN by value ***
                    if v == 2147483647 or v == -2147483648:  # Exact extreme values
                        score -= 2000  # Highest priority
                    elif abs(v) > 1000000000:  # Other large values
                        score -= 1000
                    elif 1 <= v <= 10:  # Small positive (for overflow)
                        score -= 100
                except:
                    pass
            return score
        
        sorted_combos = sorted(all_combos, key=combo_priority)
        return [list(combo) for combo in sorted_combos[:max_tests]]
    
    # 3+ parameters: corners strategy
    corners = []
    corners.append([seeds[0] for seeds in testable_seeds])
    corners.append([seeds[-1] for seeds in testable_seeds])
    corners.append([seeds[len(seeds)//2] for seeds in testable_seeds])
    
    if len(testable_seeds) > 0:
        corners.append([testable_seeds[0][0]] + [seeds[-1] for seeds in testable_seeds[1:]])
        corners.append([testable_seeds[0][-1]] + [seeds[0] for seeds in testable_seeds[1:]])
    
    max_len = max(len(seeds) for seeds in testable_seeds)
    for i in range(min(max_tests - len(corners), max_len)):
        combo = [seeds[i % len(seeds)] for seeds in testable_seeds]
        if combo not in corners:
            corners.append(combo)
    
    return corners[:max_tests]

# ─────────────────────────────────────────────────────────────────────
# Edge harness generation (CMocka-based deterministic tests)
# ─────────────────────────────────────────────────────────────────────
def _emit_edge_harness_src(func: str, param_types: Sequence[str], edges: Sequence[Set[str]]) -> str:
    """Generate CMocka test harness with edge cases for deterministic testing."""
    out: List[str] = [
        '#include <stdarg.h>',
        '#include <stddef.h>',
        '#include <setjmp.h>',
        '#include <cmocka.h>',
        '#include <limits.h>',
        '#include <stdint.h>',
        '#include <string.h>',
        '',
        '#include "test_common.h"',
        ''
    ]

    needs_ctx = _needs_protocol_ctx(param_types)
    is_reset_ctx = (func == "reset_ctx")

    # Generate seed arrays for each parameter
    seeds_per_param: List[List[str]] = []
    for i, pt in enumerate(param_types):
        if needs_ctx and i == 0:
            seeds_per_param.append([])
            continue
        
        # Prefer per-function edges if supplied; otherwise consult config.GENERIC_EDGES
        seed_set_raw = _ordered_seeds(edges[i]) if (i < len(edges) and edges[i] is not None) else []
        vals = _seed_list(pt, seed_set_raw)
        
        arr_name = f"a{i}_vals"
        init = ", ".join(vals)
        out.append(f'static {pt} {arr_name}[] = {{ {init} }};')
        out.append(f'#define {arr_name}_LEN (sizeof({arr_name})/sizeof({arr_name}[0]))')
        seeds_per_param.append(vals)

    if param_types:
        out.append("")

    # Generate test combinations
    test_combinations = _generate_test_combinations(seeds_per_param, needs_ctx, max_tests=12)

    # Generate individual test functions
    test_names: List[str] = []
    for combo_idx, combo_values in enumerate(test_combinations):
        tname = f"test_{func}_edge_{combo_idx+1}"
        test_names.append(tname)
        body: List[str] = [
            f"static void {tname}(void **state) {{",
            "    (void)state;",
        ]

        # Setup ProtocolContext if needed
        if needs_ctx:
            body.append("    ProtocolContext ctx;")
            if not is_reset_ctx:
                body.append("    reset_ctx(&ctx);")
                body.append("    ctx.authenticated = 1;")
                body.append("    ctx.state = STATE_WAIT_SERVO;")

        # Declare and initialize parameters with values from combination
        value_idx = 0
        for i, pt in enumerate(param_types):
            if needs_ctx and i == 0:
                continue
            
            # Get value from combination
            if value_idx < len(combo_values):
                val = combo_values[value_idx]
            else:
                val = '0' if not _is_string(pt) else '""'
            
            # Declare and assign
            if _is_string(pt):
                body.append(f'    {pt} a{i} = {val};')
            elif _is_pointer(pt):
                body.append(f'    {pt} a{i} = {val};')
            else:
                body.append(f'    {pt} a{i} = ({pt}){val};')
            
            value_idx += 1

        # Make the actual function call
        call_args = []
        for i in range(len(param_types)):
            call_args.append("&ctx" if (needs_ctx and i == 0) else f"a{i}")

        body.append("")
        body.append("    /* Call target function */")
        body.append(f"    {func}(" + ", ".join(call_args) + ");")
        body.append("")
        body.append("    /* Test passes if no crash/assertion */")
        body.append("}")

        out.append("\n".join(body))
        out.append("")

    # Generate main function with test runner
    out += [
        "int main(void) {",
        "    const struct CMUnitTest tests[] = {",
    ]
    for tn in test_names:
        out.append(f"        cmocka_unit_test({tn}),")
    out += [
        "    };",
        f'    return cmocka_run_group_tests_name("deterministic_edge_{func}", tests, NULL, NULL);',
        "}",
        "",
    ]
    return "\n".join(out)

# ─────────────────────────────────────────────────────────────────────
# libFuzzer harness generation (Random fuzzing)
# ─────────────────────────────────────────────────────────────────────
def _emit_libfuzzer_harness_src(func: str, param_types: Sequence[str]) -> str:
    """Generate libFuzzer harness for random fuzzing, honoring FZ_MAX_LEN."""
    out: List[str] = [
        '#include <stdint.h>',
        '#include <stddef.h>',
        '#include <string.h>',
        '#include <stdlib.h>',
        '',
        '#include "test_common.h"',
        '',
        f'#define AFZ_FZ_MAX_LEN {int(FZ_MAX_LEN)}',
        '',
    ]

    needs_ctx = _needs_protocol_ctx(param_types)
    has_strings = any(_is_string(pt) for pt in param_types)

    # Special case for Protocol_ProcessCommand(ctx, char*)
    if func == "Protocol_ProcessCommand" and len(param_types) == 2 and _is_string(param_types[1]):
        return "\n".join([
            '#include <stdint.h>',
            '#include <stddef.h>',
            '#include <string.h>',
            '#include "test_common.h"',
            '',
            f'#define AFZ_FZ_MAX_LEN {int(FZ_MAX_LEN)}',
            '',
            '/* Random fuzzer for Protocol_ProcessCommand */',
            'int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {',
            '    if (!data || size == 0) return 0;',
            '    size_t n = size < (AFZ_FZ_MAX_LEN-1) ? size : (AFZ_FZ_MAX_LEN-1);',
            '    char buf[AFZ_FZ_MAX_LEN];',
            '    memcpy(buf, data, n);',
            '    buf[n] = \'\\0\';',
            '    ProtocolContext ctx;',
            '    reset_ctx(&ctx);',
            '    ctx.authenticated = 1;',
            '    ctx.state = STATE_WAIT_SERVO;',
            '    Protocol_ProcessCommand(&ctx, buf);',
            '    return 0;',
            '}',
            '',
        ])

    # Generic string-based fuzzing
    if has_strings:
        out += [
            f'/* Random fuzzer for {func} */',
            'int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {',
            '    if (!data || size == 0) return 0;',
            '    size_t n = size < (AFZ_FZ_MAX_LEN-1) ? size : (AFZ_FZ_MAX_LEN-1);',
            '    char buf[AFZ_FZ_MAX_LEN];',
            '    memcpy(buf, data, n);',
            '    buf[n] = \'\\0\';',
            '',
        ]

        if needs_ctx:
            out += [
                '    /* Setup protocol context */',
                '    ProtocolContext ctx;',
                '    reset_ctx(&ctx);',
                '    ctx.authenticated = 1;',
                '    ctx.state = STATE_WAIT_SERVO;',
                '',
            ]

        # Build call arguments
        call_args = []
        for i, pt in enumerate(param_types):
            if needs_ctx and i == 0:
                call_args.append("&ctx")
            elif _is_string(pt):
                call_args.append("buf")
            elif _is_pointer(pt):
                call_args.append("NULL")
            else:
                call_args.append("0")

        out += [
            '    /* Call target function with fuzzer input */',
            f'    {func}(' + ", ".join(call_args) + ');',
            '    return 0;',
            '}',
            '',
        ]
        return "\n".join(out)

    # Non-string fuzzing (use data bytes as integers)
    out += [
        f'/* Random fuzzer for {func} */',
        'int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {',
        f'    if (!data || size < {max(1, len(param_types) * 4)}) return 0;',
        '',
    ]

    if needs_ctx:
        out += [
            '    /* Setup protocol context */',
            '    ProtocolContext ctx;',
            '    reset_ctx(&ctx);',
            '    ctx.authenticated = 1;',
            '    ctx.state = STATE_WAIT_SERVO;',
            '',
        ]

    # Extract integers from data bytes
    offset = 0
    for i, pt in enumerate(param_types):
        if needs_ctx and i == 0:
            continue
        if _is_pointer(pt) and not _is_string(pt):
            out.append(f'    {pt} a{i} = NULL;')
        elif _is_signed32(pt):
            out.append(f'    int32_t a{i};')
            out.append(f'    memcpy(&a{i}, data + {offset}, sizeof(int32_t));')
            offset += 4
        else:
            out.append(f'    {pt} a{i} = ({pt})(data[{offset}]);')
            offset += 1

    out.append('')

    # Build call
    call_args = []
    for i in range(len(param_types)):
        call_args.append("&ctx" if (needs_ctx and i == 0) else f"a{i}")

    out += [
        '    /* Call target function with fuzzer-derived inputs */',
        f'    {func}(' + ", ".join(call_args) + ');',
        '    return 0;',
        '}',
        '',
    ]
    return "\n".join(out)

# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────
def _write(out_dir: Path, name: str, src: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / name).write_text(src, encoding="utf-8")

def emit_edge_harness(func, *rest):
    """Emit CMocka-based deterministic edge case tests."""
    if len(rest) == 3:
        param_types, edges, out_dir = rest
    elif len(rest) == 4:
        _rtype, param_types, edges, out_dir = rest
    else:
        raise TypeError("emit_edge_harness expects 4 or 5 positional args total")
    src = _emit_edge_harness_src(func, param_types, edges)
    _write(out_dir, f"deterministic_edge_{func}.c", src)

def emit_libfuzzer_harness(func, *rest):
    """Emit libFuzzer harness for random fuzzing."""
    if len(rest) == 3:
        param_types, _edges, out_dir = rest
    elif len(rest) == 4:
        _rtype, param_types, _edges, out_dir = rest
    else:
        raise TypeError("emit_libfuzzer_harness expects 4 or 5 positional args total")
    src = _emit_libfuzzer_harness_src(func, param_types)
    _write(out_dir, f"random_fuzz_{func}.c", src)

def emit_deterministic_harness(func, *rest):
    """Alias for emit_edge_harness."""
    return emit_edge_harness(func, *rest)

__all__ = [
    "emit_edge_harness",
    "emit_deterministic_harness",
    "emit_libfuzzer_harness",
]