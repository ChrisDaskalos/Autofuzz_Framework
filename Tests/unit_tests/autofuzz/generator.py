# File: autofuzz/generator.py
from pathlib import Path
from typing import Sequence, Set, List, Any, Dict
import re

# Pull everything we need from config.py
from .config import EDGE_CAP, STRING_SEEDS, GENERIC_EDGES, FZ_MAX_LEN

# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
_PROTOCTX_PTR = re.compile(r"\bProtocolContext\s*\*")

def _clean_type(pt: str) -> str:
    # normalize whitespace and drop duplicate spaces, keep pointer stars
    t = pt.replace("const", "").strip()
    t = " ".join(t.split())
    t = t.replace(" *", "*").replace("* ", "*")
    return t

def _canonical_key_for_generic(pt: str) -> str:
    """
    Map a parameter type to a key that likely exists in GENERIC_EDGES.
    Falls back to the original string if already a direct hit.
    """
    raw = pt.strip()
    t = _clean_type(raw)

    # direct hits first
    if t in GENERIC_EDGES:
        return t

    # common synonyms / normalizations
    # note: we intentionally keep spaces in 'unsigned int'
    synonyms: Dict[str, str] = {
        "signed int": "int",
        "int32_t": "int32_t",
        "uint32_t": "uint32_t",
        "size_t": "size_t",
        "ssize_t": "ssize_t",
        "unsigned": "unsigned int",
        "unsigned int": "unsigned int",
        "long": "int64_t",         # conservative mapping
        "unsigned long": "uint64_t",
        "long long": "int64_t",
        "unsigned long long": "uint64_t",
        "char*": "const char *",   # route string-y types to config string seeds
        "char *": "const char *",
    }

    if t in synonyms and synonyms[t] in GENERIC_EDGES:
        return synonyms[t]

    # last resort: try the original (un-cleaned) and a few variations
    candidates = [raw, raw.replace("const", "").strip(), t.replace(" *", "*")]
    for c in candidates:
        if c in GENERIC_EDGES:
            return c

    return t  # may not exist; caller will handle fallback

def _is_string(pt: str) -> bool:
    t = _clean_type(pt)
    t_nospace = t.replace(" ", "")
    return t_nospace in ("char*",) or "char*" in t_nospace  # tolerate odd spellings

def _is_pointer(pt: str) -> bool:
    return "*" in pt

def _is_signed32(pt: str) -> bool:
    t = _clean_type(pt)
    return t in ("int", "signed int", "int32_t")

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

def _lookup_generic_edges_for_type(pt: str) -> List[Any]:
    """
    Ask config.GENERIC_EDGES for this parameter's canonical edge values.
    If it's a string, prefer STRING_SEEDS from config.
    """
    if _is_string(pt):
        return STRING_SEEDS[:EDGE_CAP] if STRING_SEEDS else ['""']
    key = _canonical_key_for_generic(pt)
    vals = GENERIC_EDGES.get(key)
    if vals:
        return vals[:EDGE_CAP]
    # Unknown type fallback
    if _is_pointer(pt):
        return ['NULL']
    return ['0', '1', '-1', 'INT_MAX', 'INT_MIN']

def _seed_list(pt: str, seeds: List[Any]) -> List[str]:
    """
    Turn a list of raw seeds (ints/strings) into C tokens, or
    use config-backed GENERIC_EDGES/STRING_SEEDS when seeds are missing.
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

    return out or (['""'] if _is_string(pt) else (['NULL'] if _is_pointer(pt) else ['0']))

def _auto_case_count(arr_lens: List[int]) -> int:
    arr_lens = [n for n in arr_lens if n > 0]
    if not arr_lens:
        return 1
    return max(1, min(12, max(arr_lens)))

def _make_arg_decl(i: int, pt: str) -> str:
    if _is_string(pt):  return f'{pt} a{i} = "";'
    if _is_pointer(pt): return f'{pt} a{i} = NULL;'
    return f'{pt} a{i} = ({pt})0;'

def _needs_protocol_ctx(param_types: Sequence[str]) -> bool:
    return bool(param_types and _PROTOCTX_PTR.search(param_types[0]))

# ─────────────────────────────────────────────────────────────────────
# Edge harness → CMocka tests (Deterministic)
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
        seed_set_raw = list(edges[i]) if (i < len(edges) and edges[i] is not None) else []
        vals = _seed_list(pt, seed_set_raw)
        arr_name = f"a{i}_vals"
        init = ", ".join(vals)
        out.append(f'static {pt} {arr_name}[] = {{ {init} }};')
        out.append(f'#define {arr_name}_LEN (sizeof({arr_name})/sizeof({arr_name}[0]))')
        seeds_per_param.append(vals)

    if param_types:
        out.append("")

    # Calculate number of test cases
    arr_lens = [(0 if (needs_ctx and i == 0) else len(v)) for i, v in enumerate(seeds_per_param)]
    total_cases = _auto_case_count(arr_lens)

    # Generate individual test functions
    test_names: List[str] = []
    for case_idx in range(total_cases):
        tname = f"test_{func}_edge_{case_idx+1}"
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

        # Declare and initialize parameters
        for i, pt in enumerate(param_types):
            if needs_ctx and i == 0:
                continue
            body.append("    " + _make_arg_decl(i, pt))

        # Set parameter values from seed arrays
        for i, pt in enumerate(param_types):
            if needs_ctx and i == 0:
                continue
            vals = seeds_per_param[i]
            if len(vals) > 0:
                idx = case_idx % len(vals)
                arr = f"a{i}_vals"
                body.append(f"    a{i} = {arr}[{idx}];")

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
# libFuzzer harness (Random fuzzing)
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
