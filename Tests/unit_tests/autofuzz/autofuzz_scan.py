#!/usr/bin/env python3
"""
autofuzz_scan.py

Walks stub C sources specified in STUB_SRCS, derives interesting values
for each parameter, and emits CMocka fuzz harnesses (fuzz_<func>.c).
"""
from __future__ import annotations

import ctypes.util
import os
import pathlib
import shutil
import subprocess
from typing import Dict, Final, List, Sequence, Set

import clang.cindex as clang
# after the other imports
EDGE_CAP = int(os.getenv("EDGE_CAP", 65536))  # pick cap via env-var

# --------------------------------------------------------------------------- #
# Paths / config                                                               #
# --------------------------------------------------------------------------- #

ROOT: Final[pathlib.Path] = pathlib.Path(__file__).resolve().parents[1]
GEN_DIR: Final[pathlib.Path] = ROOT                     # harnesses live here
STUB_SOURCES: Final[List[str]] = os.environ["STUB_SRCS"].split()



def _locate_libclang() -> str:
    """Return a usable libclang shared object (best-effort)."""
    if (p := os.getenv("CLANG_LIB")) and pathlib.Path(p).exists():
        return p
    if (cand := ctypes.util.find_library("clang")):
        return cand
    if (llvm_cfg := shutil.which("llvm-config")):
        try:
            lib_dir = subprocess.check_output(
                [llvm_cfg, "--libdir"], text=True
            ).strip()
            path = pathlib.Path(lib_dir) / "libclang.so"
            if path.exists():
                return str(path)
        except Exception:
            pass
    # last-ditch: CI image default
    return "/usr/lib/llvm-20/lib/libclang.so"


clang.Config.set_library_file(_locate_libclang())

# --------------------------------------------------------------------------- #
# Edge-value helpers                                                          #
# --------------------------------------------------------------------------- #

def _mk_int_edges(bit_width: int, signed: bool) -> List[int]:
     lo = -(1 << (bit_width - 1)) if signed else 0
     hi = (1 << (bit_width - 1)) - 1 if signed else (1 << bit_width) - 1
     core = [lo, lo + 1, -1, 0, 1, hi - 1, hi]
     return sorted(v for v in core if lo <= v <= hi)


STRING_SEEDS: Final[List[str]] = [
    '""', '" "', '"\\t"', '"\\r\\n"',
    '"B"', '"b"', '"X"', '"x"',
    '"(90,2,92)"', '"(0,1,1)"', '"(180,5,185)"',
    '"(90,2,99)"', '"(180,0,180)"', '"(181,1,182)"',
    '"(400,1,401)"', '"(255,1,0)"',
    '"(90 2 92)"', '"(90;2;92)"', '"90,2,92)"', '"(90,2,92"',
    '"(foo,bar,baz)"', '"¯\\\\_(ツ)_/¯"', '"Ω≈ç√"', '"\\x01\\x7F"',
    '"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"',  # 40×A
]


GENERIC_EDGES: Final[Dict[str, List[str | int]]] = {
    # 8-bit
    "uint8_t": _mk_int_edges(8,  False)[:EDGE_CAP],   # ← add slice
    "int8_t":  _mk_int_edges(8,  True )[:EDGE_CAP],   # ← add slice
    # 16-bit
    "uint16_t": _mk_int_edges(16, False)[:EDGE_CAP],
    "int16_t":  _mk_int_edges(16, True )[:EDGE_CAP],
    # 32-bit
    "uint32_t": _mk_int_edges(32, False)[:EDGE_CAP],
    "int32_t":  _mk_int_edges(32, True )[:EDGE_CAP],
    # 64-bit & size-related
    "uint64_t": _mk_int_edges(64, False)[:EDGE_CAP],
    "int64_t":  _mk_int_edges(64, True )[:EDGE_CAP],
    "size_t":   _mk_int_edges(64, False)[:EDGE_CAP],
    "ssize_t":  _mk_int_edges(64, True )[:EDGE_CAP],
    "const char *": STRING_SEEDS,          # leave strings untouched
}


CMP_OPS = {clang.CursorKind.BINARY_OPERATOR}
for _name in ("GREATER_THAN", "LESS_THAN", "GREATER_EQUAL", "LESS_EQUAL"):
    if hasattr(clang.CursorKind, _name):          # exists in older libclang
        CMP_OPS.add(getattr(clang.CursorKind, _name))
        
def _grab_int_literal(tok: clang.Token) -> int | None:
    try:
        return int(tok.spelling, 0)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Scanning helpers                                                            #
# --------------------------------------------------------------------------- #

def _scan_function(
    fn_cursor: clang.Cursor,
    param_types: Sequence[str],
    param_names: Sequence[str],
) -> List[Set[str]]:
    """
    Analyse one function and build a “value-set” for each formal parameter.

    * integer/string edge values come from GENERIC_EDGES
    * literals that appear in binary comparisons are added
    * every raw string literal in the body is routed to all `const char *`
    * **NEW**: numeric literals appearing in `switch … case <N>:` are injected
      into *every* integer-type parameter
    """
    # start with the generic per-type seeds
    edges: List[Set[str]] = [set(GENERIC_EDGES.get(t, [])) for t in param_types]

    string_literals: Set[str] = set()

    for node in fn_cursor.walk_preorder():

        # ---------- 1. record any naked string literal ------------------- #
        if node.kind is clang.CursorKind.STRING_LITERAL:
            string_literals.add(node.spelling)
            continue

        # ---------- 2. harvest switch-case values ------------------------ #
        if node.kind is clang.CursorKind.CASE_STMT:
            tok = next(node.get_tokens(), None)
            if tok and (ival := _grab_int_literal(tok)) is not None:
                # push label, label-1, label+1 into every *integer* parameter
                for idx, t in enumerate(param_types):
                    if t != "const char *":            # crude int/ptr filter
                        edges[idx].update(
                            {str(ival), str(ival - 1), str(ival + 1)}
                        )
            continue

        # ---------- 3. analyse simple binary comparisons ----------------- #
        if node.kind not in CMP_OPS:
            continue

        tokens = list(node.get_tokens())
        if len(tokens) != 3:                           # skip complex exprs
            continue

        lhs, _, rhs = tokens
        for ident, literal in ((lhs, rhs), (rhs, lhs)):
            if ident.kind is not clang.TokenKind.IDENTIFIER:
                continue
            if ident.spelling not in param_names:
                continue

            idx = param_names.index(ident.spelling)

            if (ival := _grab_int_literal(literal)) is not None:
                edges[idx].update(
                    {literal.spelling, str(ival - 1), str(ival + 1)}
                )
            elif (literal.kind is clang.TokenKind.LITERAL
                  and literal.spelling.startswith('"')):
                edges[idx].add(literal.spelling)

    # ---------- 4. feed gathered strings to every char* parameter -------- #
    for idx, t in enumerate(param_types):
        if t == "const char *":
            edges[idx].update(string_literals)

    return edges

# --------------------------------------------------------------------------- #
# Harness generation                                                          #
# --------------------------------------------------------------------------- #
def _emit_harness(
    func: str,
    param_types: Sequence[str],
    edges: Sequence[Set[str]],
) -> str:
    """Generate a CMocka fuzz harness for *func*."""

    #  ── truncate any huge edge-set to  literals ──
    capped = [list(s)[:EDGE_CAP] for s in edges]
    cartesian = all(len(v) <= EDGE_CAP for v in capped if v)

    out: List[str] = [
        '#include "test_common.h"',
        '#include "autofuzz/autofuzz_rt.h"',
        '#include <signal.h>',
        '#include <time.h>',
        "",
        "static unsigned long long max_cases = 0, cases_run = 0;",
        "static unsigned long long max_secs  = 0;",
        "static time_t           start       = 0;",
        "",
    ]

    # ── emit value arrays ───────────────────────────────────────────────
    for i, (pt, vals) in enumerate(zip(param_types, capped)):
        if not vals:
            continue
        arr  = f"af_arr_{i}"
        init = ", ".join(map(str, vals))
        if pt == "const char *":          # keep loop-until-NULL working
            init += ", NULL"
        out.append(f"static {pt} {arr}[] = {{ {init} }};")
        if cartesian:
            out.append(f"#define {arr}_LEN (sizeof({arr})/sizeof({arr}[0]))")

    # ── helper : call + global limit check ──────────────────────────────
    def emit_call(indent: str, call: str) -> None:
        out.append(f"{indent}{func}({call});")
        out.append(f"{indent}++cases_run;")
        out.append(
            f"{indent}if ((max_cases && cases_run >= max_cases) ||"
            f"(max_secs  && (unsigned long long)(time(NULL) - start) >= max_secs))"
        )
        out.append(f"{indent}    return;")

    # ── recursive Cartesian loop builder ───────────────────────────────
    def nest(depth: int) -> None:
        if depth == len(param_types):
            args = ", ".join(
                f"&a{j}" if pt.count('*') > 1 else f"a{j}"
                for j, pt in enumerate(param_types)
            )
            emit_call("        ", args)
            return
        if not capped[depth]:
            nest(depth + 1)
            return
        arr  = f"af_arr_{depth}"
        cond = f"{arr}[i{depth}]!=NULL" if param_types[depth] == "const char *"\
               else f"i{depth} < {arr}_LEN"
        out.append(f"        for (size_t i{depth}=0; {cond}; ++i{depth}) {{")
        out.append(f"            a{depth} = {arr}[i{depth}];")
        nest(depth + 1)
        out.append("        }")

    # ── CMocka test wrappers ────────────────────────────────────────────
    if cartesian:
        out += [f"static void test_{func}_all(void **_)",
                "{", "    (void)_;"]
        for j, pt in enumerate(param_types):
            init = "0" if not capped[j] else f"af_arr_{j}[0]"
            out.append(f"    {pt} a{j} = {init};")
        nest(0)
        out.append("}\n")
    else:
        for idx, pt in enumerate(param_types):
            if not capped[idx]:
                continue
            arr  = f"af_arr_{idx}"
            cond = f"{arr}[i]!=NULL" if pt == "const char *"\
                   else f"i < sizeof({arr})/sizeof({arr}[0])"
            out += [f"static void test_{func}_p{idx}(void **_)",
                    "{", "    (void)_;"]
            for j, pt2 in enumerate(param_types):
                init = f"{arr}[0]" if j == idx else "0"
                out.append(f"    {pt2} a{j} = {init};")
            out.append(f"    for (size_t i=0; {cond}; ++i) {{")
            out.append(f"        a{idx} = {arr}[i];")
            args = ", ".join(
                f"&a{j}" if pt2.count('*') > 1 else f"a{j}"
                for j, pt2 in enumerate(param_types)
            )
            emit_call("        ", args)
            out += ["    }", "}\n"]

    # ── main() ───────────────────────────────────────────────────────────
    out += [
        "int main(void)",
        "{",
        "    alarm(2);",
        "    const char *c=getenv(\"FUZZ_MAX_CASES\"), *s=getenv(\"FUZZ_MAX_SECS\");",
        "    if(c) max_cases = strtoull(c,0,10);",
        "    if(s) max_secs  = strtoull(s,0,10);",
        "    start = time(NULL);",
        "    const struct CMUnitTest t[] = {"
    ]
    if cartesian:
        out.append(f"        cmocka_unit_test(test_{func}_all),")
    else:
        for i, v in enumerate(capped):
            if v:
                out.append(f"        cmocka_unit_test(test_{func}_p{i}),")
    out += [
        "    };",
        "    return cmocka_run_group_tests(t, NULL, NULL);",
        "}",
        ""
    ]
    return "\n".join(out)

# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #

def run() -> None:
    idx = clang.Index.create()

    for stub in STUB_SOURCES:
        stub_name = pathlib.Path(stub).name
        tu = idx.parse(str(ROOT / stub),
                       args=["-DUNIT_TEST", "-I" + str(ROOT)])

        for cursor in tu.cursor.get_children():
            if (cursor.kind is not clang.CursorKind.FUNCTION_DECL
                    or not cursor.is_definition()):
                continue
            if pathlib.Path(cursor.location.file.name).name != stub_name:
                continue

            ptypes = [a.type.spelling for a in cursor.get_arguments()]
            pnames = [a.spelling for a in cursor.get_arguments()]
            edge_sets = _scan_function(cursor, ptypes, pnames)
            if all(not s for s in edge_sets):
                continue

            (GEN_DIR / f"fuzz_{cursor.spelling}.c").write_text(
                _emit_harness(cursor.spelling, ptypes, edge_sets),
                encoding="utf-8"
            )
            print("autofuzz -", cursor.spelling)


if __name__ == "__main__":
    run()
