# File: autofuzz/scanner.py
"""
Find the functions to test (libclang) and collect edge values for each
parameter: default values per C type (from the config), plus the literals,
comparisons and switch cases found in the function body.
"""
import pathlib
from typing import Sequence, Set, List, Optional, Tuple, Dict
from clang import cindex
from .config import Config

def arg_count(cur: cindex.Cursor) -> int:
    """Return number of formal parameters (works with old/new libclang)."""
    try:
        return cur.get_num_arguments()
    except AttributeError:
        return len(list(cur.get_arguments()))

CMP_OPS: Set[cindex.CursorKind] = {cindex.CursorKind.BINARY_OPERATOR}
for name in ("GREATER_THAN", "LESS_THAN", "GREATER_EQUAL", "LESS_EQUAL", "EQUAL_EQUAL", "NOT_EQUAL"):
    if hasattr(cindex.CursorKind, name):
        CMP_OPS.add(getattr(cindex.CursorKind, name))

def grab_int_literal(tok: cindex.Token) -> Optional[int]:
    """Return integer literal value or None if unparsable."""
    try:
        return int(tok.spelling, 0)
    except ValueError:
        return None

def extract_string_literal(node: cindex.Cursor) -> Optional[str]:
    """Extract string literal with proper escaping."""
    if node.kind == cindex.CursorKind.STRING_LITERAL:
        return node.spelling
    return None

# ─────────────────────────────────────────────────────────────────────
# FIXED: Extract character literals as strings
# ─────────────────────────────────────────────────────────────────────
def extract_character_literal(node: cindex.Cursor) -> Optional[str]:
    """
    Extract character literal and convert to string.
    E.g., 'A' becomes "A", '1' becomes "1"
    """
    if node.kind == cindex.CursorKind.CHARACTER_LITERAL:
        tokens = list(node.get_tokens())
        if tokens:
            char_lit = tokens[0].spelling  # e.g., "'1'"
            if len(char_lit) >= 3 and char_lit[0] == "'" and char_lit[-1] == "'":
                char_value = char_lit[1:-1]  # Extract the character
                return f'"{char_value}"'  # Convert to string literal format
    return None

class DomainConstraint:
    """Represents constraints on a parameter's valid domain."""
    def __init__(self, param_name: str, param_type: str, generic: Dict[str, list]):
        self.generic = generic
        self.param_name = param_name
        self.param_type = param_type
        self.min_value: Optional[int] = None
        self.max_value: Optional[int] = None
        self.exact_values: Set[int] = set()
        self.string_patterns: Set[str] = set()
        self.null_checked = False
        self.range_checked = False
        
    def add_comparison(self, op: str, value: int):
        """Add constraint from comparison operator."""
        if op in ['>', '>=']:
            min_val = value if op == '>=' else value + 1
            self.min_value = max(self.min_value, min_val) if self.min_value else min_val
            self.range_checked = True
        elif op in ['<', '<=']:
            max_val = value if op == '<=' else value - 1
            self.max_value = min(self.max_value, max_val) if self.max_value else max_val
            self.range_checked = True
        elif op in ['==']:
            self.exact_values.add(value)
        elif op in ['!=']:
            pass
            
    def get_edge_values(self) -> Set[str]:
        """Generate edge values based on constraints."""
        edges = set()
        
        if self.min_value is not None:
            edges.update({
                str(self.min_value - 1),
                str(self.min_value),
                str(self.min_value + 1),
            })
        
        if self.max_value is not None:
            edges.update({
                str(self.max_value - 1),
                str(self.max_value),
                str(self.max_value + 1),
            })
        
        edges.update(str(v) for v in self.exact_values)
        
        if not edges and self.param_type != "const char *":
            edges.update(map(str, self.generic.get(self.param_type, [0, 1, -1])))
        
        return edges

def scan_function_enhanced(
    fn_cursor: cindex.Cursor,
    param_types: Sequence[str],
    param_names: Sequence[str],
    cfg: Config,
) -> Tuple[List[Set[str]], List[DomainConstraint]]:
    """Analyse function and return both edge values and domain constraints."""
    constraints = [DomainConstraint(name, ptype, cfg.generic_edges)
                  for name, ptype in zip(param_names, param_types)]
    
    edges: List[Set[str]] = [set(cfg.generic_edges.get(t, [])) for t in param_types]
    string_literals: Set[str] = set()
    
    param_index = {name: i for i, name in enumerate(param_names)}
    
    for node in fn_cursor.walk_preorder():
        # 1. Collect string literals
        if node.kind == cindex.CursorKind.STRING_LITERAL:
            lit = extract_string_literal(node)
            if lit:
                string_literals.add(lit)
                parent = node.semantic_parent
                if parent and parent.kind in CMP_OPS:
                    _analyze_string_comparison(parent, param_names, constraints, lit)
            continue
        
        # *** FIXED: Collect character literals ***
        if node.kind == cindex.CursorKind.CHARACTER_LITERAL:
            lit = extract_character_literal(node)
            if lit:
                string_literals.add(lit)  # Add as string for testing
            continue
        
        # 2. Analyze NULL checks
        if node.kind == cindex.CursorKind.BINARY_OPERATOR:
            _analyze_null_check(node, param_names, constraints)
        
        # 3. Switch case analysis
        if node.kind == cindex.CursorKind.CASE_STMT:
            _analyze_switch_case(node, param_names, param_index, edges, constraints, string_literals)
            continue
        
        # 4. Comparison analysis
        if node.kind in CMP_OPS:
            _analyze_comparison(node, param_names, param_index, edges, constraints)
            continue
        
        # 5. Function call analysis
        if node.kind == cindex.CursorKind.CALL_EXPR:
            _analyze_function_call(node, param_names, constraints)
    
    # Apply constraints to generate final edge values
    for i, constraint in enumerate(constraints):
        # *** FIXED: Normalize type for comparison ***
        normalized_type = param_types[i].replace("const", "").strip()
        normalized_type = " ".join(normalized_type.split())
        
        is_string_type = "char" in normalized_type and "*" in normalized_type
        
        if not is_string_type:
            edges[i].update(constraint.get_edge_values())
        else:
            # For strings, use collected literals plus defaults
            edges[i].update(string_literals)
            edges[i].update(cfg.string_seeds)
            edges[i].update(constraint.string_patterns)

    # limits.int_ranges in the YAML: the valid range of one parameter.
    for i, name in enumerate(param_names):
        rng = cfg.int_range(fn_cursor.spelling, name)
        if rng is not None:
            edges[i] = int_range_edges(rng[0], rng[1])

    return edges, constraints

def int_range_edges(lo: int, hi: int) -> Set[str]:
    """Values just outside, on, and just inside both ends of [lo, hi]."""
    vals = {lo - 1, lo, lo + 1, (lo + hi) // 2, hi - 1, hi, hi + 1}
    return {str(v) for v in vals}

def _analyze_comparison(
    node: cindex.Cursor,
    param_names: List[str],
    param_index: Dict[str, int],
    edges: List[Set[str]],
    constraints: List[DomainConstraint]
):
    """Extract constraints from comparison operators."""
    tokens = list(node.get_tokens())
    if len(tokens) < 3:
        return
    
    op_spelling = None
    for tok in tokens:
        if tok.spelling in ['<', '>', '<=', '>=', '==', '!=']:
            op_spelling = tok.spelling
            break
    
    if not op_spelling:
        return
    
    for ident, lit in [(tokens[0], tokens[-1]), (tokens[-1], tokens[0])]:
        if ident.kind != cindex.TokenKind.IDENTIFIER:
            continue
        if ident.spelling not in param_names:
            continue
        
        idx = param_index[ident.spelling]
        val = grab_int_literal(lit)
        
        if val is not None:
            constraints[idx].add_comparison(op_spelling, val)
            edges[idx].update({
                str(val - 1), str(val), str(val + 1)
            })

# ─────────────────────────────────────────────────────────────────────
# FIXED: Switch case analysis with character literal support
# ─────────────────────────────────────────────────────────────────────
def _analyze_switch_case(
    node: cindex.Cursor,
    param_names: List[str],
    param_index: Dict[str, int],
    edges: List[Set[str]],
    constraints: List[DomainConstraint],
    string_literals: Set[str]
):
    """Extract values from switch cases."""
    case_tokens = list(node.get_tokens())
    if not case_tokens:
        return
    
    # Try to get integer value
    val = grab_int_literal(case_tokens[0])
    
    # *** FIXED: Also handle character literals in switch cases ***
    if val is None and case_tokens[0].kind == cindex.TokenKind.LITERAL:
        spelling = case_tokens[0].spelling
        if len(spelling) >= 3 and spelling[0] == "'" and spelling[-1] == "'":
            # It's a character literal like '1'
            char_value = spelling[1:-1]
            string_literals.add(f'"{char_value}"')  # Add as string
            val = ord(char_value) if len(char_value) == 1 else None
    
    if val is None:
        return
    
    switch_stmt = node.semantic_parent
    if not switch_stmt or switch_stmt.kind != cindex.CursorKind.SWITCH_STMT:
        return
    
    for child in switch_stmt.get_children():
        if child.kind == cindex.CursorKind.DECL_REF_EXPR:
            ref_name = child.spelling
            if ref_name in param_names:
                idx = param_index[ref_name]
                constraints[idx].exact_values.add(val)
                edges[idx].update({str(val - 1), str(val), str(val + 1)})
                break

def _analyze_null_check(
    node: cindex.Cursor,
    param_names: List[str],
    constraints: List[DomainConstraint]
):
    """Detect NULL pointer checks."""
    tokens = list(node.get_tokens())
    if len(tokens) >= 3:
        for tok in tokens:
            if tok.spelling in param_names:
                idx = param_names.index(tok.spelling)
                if any(t.spelling == "NULL" for t in tokens):
                    constraints[idx].null_checked = True

def _analyze_function_call(
    node: cindex.Cursor,
    param_names: List[str],
    constraints: List[DomainConstraint]
):
    """Analyze function calls for range checks."""
    if not node.spelling:
        return
    
    if node.spelling in ['assert', 'clamp', 'min', 'max', 'CLAMP', 'MIN', 'MAX']:
        for arg in node.get_arguments():
            tokens = list(arg.get_tokens())
            for tok in tokens:
                if tok.spelling in param_names:
                    idx = param_names.index(tok.spelling)
                    constraints[idx].range_checked = True

def _analyze_string_comparison(
    node: cindex.Cursor,
    param_names: List[str],
    constraints: List[DomainConstraint],
    string_lit: str
):
    """Analyze string comparisons to extract patterns."""
    tokens = list(node.get_tokens())
    for tok in tokens:
        if tok.spelling in param_names:
            idx = param_names.index(tok.spelling)
            normalized = constraints[idx].param_type.replace("const", "").strip()
            if "char" in normalized and "*" in normalized:
                constraints[idx].string_patterns.add(string_lit)

def scan_function(
    fn_cursor: cindex.Cursor,
    param_types: Sequence[str],
    param_names: Sequence[str],
    cfg: Config,
) -> List[Set[str]]:
    """Analyse one function and return edge values."""
    edges, _ = scan_function_enhanced(fn_cursor, param_types, param_names, cfg)
    return edges

def extract_targets(
    tu: cindex.TranslationUnit,
    source: pathlib.Path,
) -> List[cindex.Cursor]:
    """Return the non-static functions defined in `source` itself."""
    want = pathlib.Path(source).resolve()
    targets: List[cindex.Cursor] = []
    for cur in tu.cursor.get_children():
        if (
            cur.kind is not cindex.CursorKind.FUNCTION_DECL
            or not cur.is_definition()
        ):
            continue
        if cur.location.file is None or pathlib.Path(cur.location.file.name).resolve() != want:
            continue
        if cur.linkage is cindex.LinkageKind.INTERNAL:
            continue
        targets.append(cur)
    return targets

# ─────────────────────────────────────────────────────────────────────
# Skip detection: code that cannot run on a PC
# ─────────────────────────────────────────────────────────────────────
_ASM_KINDS = {getattr(cindex.CursorKind, k) for k in ("ASM_STMT", "MS_ASM_STMT") if hasattr(cindex.CursorKind, k)}
_LOOP_KINDS = {cindex.CursorKind.WHILE_STMT, cindex.CursorKind.DO_STMT, cindex.CursorKind.FOR_STMT}
_BREAK_SCOPES = _LOOP_KINDS | {cindex.CursorKind.SWITCH_STMT}
_CONST_EXPR_KINDS = {
    cindex.CursorKind.INTEGER_LITERAL, cindex.CursorKind.PAREN_EXPR, cindex.CursorKind.UNEXPOSED_EXPR,
    cindex.CursorKind.CSTYLE_CAST_EXPR, cindex.CursorKind.BINARY_OPERATOR, cindex.CursorKind.UNARY_OPERATOR,
}


_eval_ready = False


def _eval_int(cur: cindex.Cursor) -> Optional[int]:
    """The value of a constant integer expression (macros expanded), or None.
    Uses clang_Cursor_Evaluate from libclang (clang >= 3.9)."""
    global _eval_ready
    import ctypes
    lib = cindex.conf.lib
    try:
        if not _eval_ready:
            lib.clang_Cursor_Evaluate.argtypes = [cindex.Cursor]
            lib.clang_Cursor_Evaluate.restype = ctypes.c_void_p
            lib.clang_EvalResult_getKind.argtypes = [ctypes.c_void_p]
            lib.clang_EvalResult_getKind.restype = ctypes.c_int
            lib.clang_EvalResult_getAsLongLong.argtypes = [ctypes.c_void_p]
            lib.clang_EvalResult_getAsLongLong.restype = ctypes.c_longlong
            lib.clang_EvalResult_dispose.argtypes = [ctypes.c_void_p]
            lib.clang_EvalResult_dispose.restype = None
            _eval_ready = True
        res = lib.clang_Cursor_Evaluate(cur)
    except (AttributeError, ctypes.ArgumentError):
        return None
    if not res:
        return None
    try:
        return lib.clang_EvalResult_getAsLongLong(res) if lib.clang_EvalResult_getKind(res) == 1 else None
    finally:
        lib.clang_EvalResult_dispose(res)


def _int_const_to_pointer(cast: cindex.Cursor) -> bool:
    """(T *)0x40010810 or (T *)(PERIPH_BASE + 0x400): a register address.
    (T *)0 (NULL) does not count."""
    if cast.type.get_canonical().kind != cindex.TypeKind.POINTER:
        return False
    operand = [c for c in cast.get_children() if c.kind != cindex.CursorKind.TYPE_REF]
    if len(operand) != 1:
        return False
    for node in operand[0].walk_preorder():
        if node.kind not in _CONST_EXPR_KINDS and node.kind != cindex.CursorKind.TYPE_REF:
            return False   # uses a variable, a call, ...: not a constant address
    if operand[0].type.get_canonical().kind == cindex.TypeKind.POINTER:
        return False       # (T *)(void *)x: a pointer-to-pointer cast
    value = _eval_int(operand[0])
    return value is not None and value != 0


def _always_true_loop(loop: cindex.Cursor) -> bool:
    toks = [t.spelling for t in loop.get_tokens()]
    if loop.kind == cindex.CursorKind.FOR_STMT:
        # for ( init ; ; step ): nothing between the two ';' at depth 1
        depth, semis = 0, []
        for i, t in enumerate(toks):
            if t == "(":
                depth += 1
            elif t == ")":
                depth -= 1
                if depth == 0:
                    break
            elif t == ";" and depth == 1:
                semis.append(i)
        return len(semis) == 2 and semis[1] == semis[0] + 1
    if loop.kind == cindex.CursorKind.WHILE_STMT and len(toks) >= 4 and toks[1] == "(" and toks[3] == ")":
        cond = toks[2]
    elif loop.kind == cindex.CursorKind.DO_STMT and len(toks) >= 4 and toks[-1] in (")", ";"):
        tail = toks[-4:] if toks[-1] == ")" else toks[-5:-1]
        if tail[0] != "(" or tail[2] != ")":
            return False
        cond = tail[1]
    else:
        return False
    if cond == "true":
        return True
    try:
        return int(cond.rstrip("uUlL"), 0) != 0
    except ValueError:
        return False


def _can_leave(node: cindex.Cursor, loop_level: bool = True) -> bool:
    """True if a return, goto or a break of THIS loop is inside `node`."""
    for child in node.get_children():
        if child.kind in (cindex.CursorKind.RETURN_STMT, cindex.CursorKind.GOTO_STMT):
            return True
        if child.kind == cindex.CursorKind.BREAK_STMT and loop_level:
            return True
        if _can_leave(child, loop_level and child.kind not in _BREAK_SCOPES):
            return True
    return False


def skip_reason(fn: cindex.Cursor) -> Optional[str]:
    """Why this function cannot be tested on a PC, or None if it can."""
    for node in fn.walk_preorder():
        if node.kind in _ASM_KINDS:
            return "inline assembly (runs only on the target CPU)"
        if node.kind == cindex.CursorKind.CSTYLE_CAST_EXPR and _int_const_to_pointer(node):
            return "casts an integer constant to a pointer (hardware register access)"
        if node.kind in _LOOP_KINDS and _always_true_loop(node) and not _can_leave(node):
            return "never returns (endless loop with no break or return)"
    return None


# ---------------------------------------------------------------------------
# Which pointer parameters can get a zero-filled object instead of NULL
# ---------------------------------------------------------------------------
PROBE_FILE = "__autofuzz_probe.c"


def _creatable(pointee: cindex.Type) -> bool:
    """True if `<pointee> x = {0};` compiles: a complete object type."""
    canon = pointee.get_canonical()
    if canon.kind in (cindex.TypeKind.VOID, cindex.TypeKind.FUNCTIONPROTO,
                      cindex.TypeKind.FUNCTIONNOPROTO):
        return False
    spelling = pointee.spelling
    if "(" in spelling or "[" in spelling:   # arrays, function pointers: no simple declaration
        return False
    return pointee.get_size() > 0            # < 0: incomplete (e.g. an opaque struct)


def zero_fill_types(param_types: Sequence[str], cfg: Config,
                    index: Optional[cindex.Index] = None) -> Dict[str, str]:
    """
    {pointer type: pointee type} for the pointer parameters (not `char *`)
    that a generated test can create as a zero-filled object.

    The check is done as the generated test sees the types: only with the
    headers in harness.includes. A struct that the header only declares
    (`struct sensor;`) is incomplete there, so it keeps NULL. So do void *
    and function pointers. If the headers do not parse, everything keeps NULL.
    """
    wanted = sorted({pt for pt in param_types
                     if "*" in pt and "char*" not in pt.replace("const", "").replace(" ", "")})
    if not wanted:
        return {}
    index = index or cindex.Index.create()
    lines = [f'#include "{h}"' for h in cfg.harness_includes]
    lines += [f"{pt} autofuzz_probe_{i};" for i, pt in enumerate(wanted)]
    probe = str(cfg.base_dir / PROBE_FILE)
    try:
        tu = index.parse(probe, args=cfg.clang_args(),
                         unsaved_files=[(probe, "\n".join(lines) + "\n")])
    except cindex.TranslationUnitLoadError:
        return {}
    if any(d.severity >= cindex.Diagnostic.Error for d in tu.diagnostics):
        return {}
    out: Dict[str, str] = {}
    for cur in tu.cursor.get_children():
        if cur.kind != cindex.CursorKind.VAR_DECL or not cur.spelling.startswith("autofuzz_probe_"):
            continue
        pt = wanted[int(cur.spelling[len("autofuzz_probe_"):])]
        pointee = cur.type.get_pointee()
        if _creatable(pointee):
            out[pt] = pointee.spelling
    return out
