"""
Generate stubs for what the sources use but do not define.

Firmware code calls HAL functions (HAL_UART_Transmit, HAL_Delay, ...) and
uses global handles (huart2, htim2, ...) that live in other files or in a
library. On the PC they are missing at link time. This module finds them with
libclang and writes <output_dir>/stubs/stubs.c:

  * a global gets a definition with the type from its `extern` declaration;
  * a function gets a body that counts its calls and returns 0
    (0 is HAL_OK, NULL for a pointer, a zeroed struct for a struct).

Only declarations from your own headers (include_dirs, fake_include_dirs)
are stubbed. Functions from system headers (libc) are not.

Same sources -> the same stubs.c (sorted by name, no timestamps).
"""
from pathlib import Path
from typing import Dict, List, Optional

from clang import cindex

from .config import Config

STUBS_FILE = "stubs.c"
_GLOBAL_KINDS = (cindex.CursorKind.FUNCTION_DECL, cindex.CursorKind.VAR_DECL)


class Stubs:
    """What stubgen found. `pointer_returns` = stubs that always return NULL."""

    def __init__(self):
        self.functions: Dict[str, cindex.Cursor] = {}
        self.globals: Dict[str, cindex.Cursor] = {}
        self.headers: List[str] = []
        self.pointer_returns: List[str] = []
        self.not_stubbed: List[str] = []   # "name: reason"

    def names(self) -> List[str]:
        return sorted(list(self.functions) + list(self.globals))


def _same_file(cur: cindex.Cursor, files: set) -> bool:
    f = cur.location.file
    return f is not None and str(Path(f.name).resolve()) in files


def _is_global(cur: cindex.Cursor) -> bool:
    parent = cur.semantic_parent
    return parent is not None and parent.kind == cindex.CursorKind.TRANSLATION_UNIT


def _defined_names(tus: List[cindex.TranslationUnit], src_files: set) -> set:
    """Functions and globals defined in the sources (static ones too)."""
    names = set()
    for tu in tus:
        for cur in tu.cursor.get_children():
            if cur.kind in _GLOBAL_KINDS and cur.is_definition() and _same_file(cur, src_files):
                names.add(cur.spelling)
            # A static inline function in a header is defined too
            if cur.kind == cindex.CursorKind.FUNCTION_DECL and cur.is_definition():
                names.add(cur.spelling)
    return names


def _include_name(header: Path, cfg: Config) -> str:
    """How stubs.c includes a header: relative to the first include folder
    that contains it (so the text is the same on every machine)."""
    for d in cfg.fake_include_dirs + cfg.include_dirs:
        try:
            return header.resolve().relative_to(Path(d).resolve()).as_posix()
        except ValueError:
            continue
    return header.resolve().as_posix()


def find(cfg: Config, index: Optional[cindex.Index] = None) -> Stubs:
    index = index or cindex.Index.create()
    src_files = {str(Path(s).resolve()) for s in cfg.sources}
    tus = []
    for src in cfg.sources:
        try:
            tus.append(index.parse(str(src), args=cfg.clang_args()))
        except cindex.TranslationUnitLoadError:
            continue
    defined = _defined_names(tus, src_files)

    found = Stubs()
    header_order: List[str] = []
    for tu in tus:
        for node in tu.cursor.walk_preorder():
            if node.kind not in (cindex.CursorKind.DECL_REF_EXPR, cindex.CursorKind.CALL_EXPR):
                continue
            if not _same_file(node, src_files):
                continue  # only what the sources themselves use
            ref = node.referenced
            if ref is None or ref.kind not in _GLOBAL_KINDS or not _is_global(ref):
                continue
            name = ref.spelling
            if name in defined or name in found.functions or name in found.globals:
                continue
            if ref.location.file is None or ref.location.is_in_system_header:
                continue  # compiler builtin or libc
            if ref.kind == cindex.CursorKind.FUNCTION_DECL:
                found.functions[name] = ref
            else:
                found.globals[name] = ref
            inc = _include_name(Path(ref.location.file.name), cfg)
            if inc not in header_order:
                header_order.append(inc)
    found.headers = header_order
    return found


# ---------------------------------------------------------------------------
# Writing stubs.c
# ---------------------------------------------------------------------------
def _param_decl(i: int, ptype: cindex.Type) -> str:
    spelling = ptype.spelling
    if "(" in spelling:   # function pointer etc.: leave the name out
        return spelling
    if ptype.kind in (cindex.TypeKind.CONSTANTARRAY, cindex.TypeKind.INCOMPLETEARRAY):
        return f"{ptype.element_type.spelling} a{i}[]"
    return f"{spelling} a{i}"


def _function_stub(name: str, decl: cindex.Cursor, found: Stubs) -> List[str]:
    ftype = decl.type
    rtype = decl.result_type
    if ftype.kind == cindex.TypeKind.FUNCTIONNOPROTO:
        params = ""
    else:
        args = [_param_decl(i, t) for i, t in enumerate(ftype.argument_types())]
        if ftype.is_function_variadic():
            args.append("...")
        params = ", ".join(args) or "void"
    lines = [f"unsigned long autofuzz_calls_{name};"]
    is_void = rtype.kind == cindex.TypeKind.VOID
    is_ptr = rtype.get_canonical().kind == cindex.TypeKind.POINTER
    if "(" in rtype.spelling:
        found.not_stubbed.append(f"{name}: its return type is too complex for a stub")
        return [f"/* {name}: not stubbed (return type {rtype.spelling}) */"]
    if is_ptr:
        found.pointer_returns.append(name)
        lines.append(f"/* WARNING: returns a pointer, always NULL. A finding after a call to {name} needs review. */")
    lines.append(f"{rtype.spelling} {name}({params})")
    lines.append("{")
    for i, t in enumerate([] if ftype.kind == cindex.TypeKind.FUNCTIONNOPROTO else ftype.argument_types()):
        if "(" not in t.spelling:
            lines.append(f"    (void)a{i};")
    lines.append(f"    autofuzz_calls_{name}++;")
    if not is_void:
        lines.append(f"    static {rtype.spelling} autofuzz_ret;   /* zero: 0, HAL_OK, NULL or a zeroed struct */")
        lines.append("    return autofuzz_ret;")
    lines.append("}")
    return lines


def write(found: Stubs, out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "/*",
        " * Generated by AutoFuzz (stubgen.py). Do not edit; it is written again on every run.",
        " * Stubs for the functions and globals that the sources use but do not define.",
        " * Each function counts its calls in autofuzz_calls_<name> and returns 0.",
        " */",
        "#include <stddef.h>",
    ]
    lines += [f'#include "{h}"' for h in found.headers]
    lines.append("")
    if not found.functions and not found.globals:
        lines.append("/* Nothing to stub: the sources define everything they use. */")
        lines.append("typedef int autofuzz_no_stubs;")
    for name in sorted(found.globals):
        lines.append(f"__typeof__({name}) {name};")
    if found.globals:
        lines.append("")
    for name in sorted(found.functions):
        lines += _function_stub(name, found.functions[name], found)
        lines.append("")
    path = out_dir / STUBS_FILE
    path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    return path


def generate(cfg: Config, out_dir: Path, quiet: bool = False) -> Stubs:
    found = find(cfg)
    write(found, out_dir)
    if not quiet:
        if found.names():
            print(f"autofuzz: stubs -> {', '.join(found.names())}")
        for name in sorted(found.pointer_returns):
            print(f"autofuzz: WARNING: stub {name}() returns a pointer (always NULL). "
                  f"A finding after a call to {name} needs review.")
        for msg in found.not_stubbed:
            print(f"autofuzz: WARNING: not stubbed: {msg}")
    return found
