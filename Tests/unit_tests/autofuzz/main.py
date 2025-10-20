# File: autofuzz/main.py
import os
import sys
import re
from pathlib import Path
from typing import List, Tuple

from clang import cindex

from .config import STUB_SOURCES
from . import scanner
from . import generator

# -------- robust helpers ----------
def _param_types_and_names(fn: cindex.Cursor) -> Tuple[List[str], List[str]]:
    pts: List[str] = []
    pns: List[str] = []
    try:
        args = list(fn.get_arguments())
    except Exception:
        args = []
    for a in args:
        try:
            pts.append(a.type.get_canonical().spelling.strip())
        except Exception:
            pts.append(a.type.spelling.strip())
        try:
            pns.append(a.spelling or f"arg{len(pns)}")
        except Exception:
            pns.append(f"arg{len(pns)}")
    return pts, pns

_SIG_RE = re.compile(
    r'(?m)^\s*(?:extern\s+)?(?P<rtype>[A-Za-z_][\w\s\*\d]*?)\s+'
    r'(?P<name>[A-Za-z_]\w*)\s*'
    r'\(\s*(?P<params>[^)]*)\)\s*;',
)

def _split_params(ps: str) -> List[str]:
    ps = ps.strip()
    if not ps or ps == "void":
        return []
    items = [p.strip() for p in ps.split(",")]
    out: List[str] = []
    for it in items:
        # drop trailing parameter identifier; keep type (incl. *)
        # e.g., "const char *s" -> "const char *"
        toks = it.split()
        if not toks:
            continue
        # If last token contains '*' (e.g. "*ctx"), keep it part of type
        if len(toks) >= 2 and not toks[-1].endswith('*'):
            # assume last token is the name
            out.append(" ".join(toks[:-1]) or toks[-1])
        else:
            out.append(" ".join(toks))
    return [t.strip() for t in out if t.strip()]

def _regex_fallback(paths: List[Path]) -> List[Tuple[str, List[str]]]:
    seen = {}
    for p in paths:
        if not p.exists():
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in _SIG_RE.finditer(txt):
            name = m.group("name")
            rtype = m.group("rtype").strip()
            params = _split_params(m.group("params"))
            if len(params) == 0:
                continue
            # skip static
            if re.search(r'\bstatic\b', rtype):
                continue
            # canonicalize common spacing
            params = [re.sub(r'\s+', ' ', t).strip() for t in params]
            seen[name] = params
    return [(k, seen[k]) for k in sorted(seen.keys())]

# -------- main flow ----------
def run() -> None:
    stub_list = [Path(s) for s in (STUB_SOURCES or ["test_common.c"])]
    # also consider sibling headers
    probe: List[Path] = []
    for p in stub_list:
        probe.append(p)
        stem = p.with_suffix("")
        for ext in (".h", ".hpp", ".c"):
            cand = stem.with_suffix(ext)
            if cand not in probe:
                probe.append(cand)

    edge_out = Path(".")   # force write where Makefile looks
    fuzz_out = Path(".")   # same

    # Try clang first
    index = cindex.Index.create()
    # parse first stub (good enough: our fallback handles the rest)
    tu = None
    for p in stub_list:
        if p.exists():
            args = []  # you can add include dirs here if needed
            try:
                tu = index.parse(str(p), args=args)
                break
            except Exception:
                continue

    targets = []
    if tu is not None:
        targets = scanner.extract_targets(tu, stub_list[0].name if stub_list else "test_common.c")

    # If clang found nothing, use regex fallback over stubs + sibling headers
    if not targets:
        pairs = _regex_fallback(probe)
        if not pairs:
            print("autofuzz: no targets found (clang+regex). Nothing to do.", file=sys.stderr)
            return
        print(f"autofuzz: regex targets -> {', '.join(n for n,_ in pairs)}")
        for name, ptypes in pairs:
            # edges empty → generator falls back to default seeds per type
            edges = [set() for _ in ptypes]
            generator.emit_deterministic_harness(name, ptypes, edges, edge_out)
            generator.emit_libfuzzer_harness(name, ptypes, edges, fuzz_out)
        return

    # clang path
    names = []
    for fn in targets:
        ptypes, pnames = _param_types_and_names(fn)
        edges = scanner.scan_function(fn, ptypes, pnames)
        names.append(fn.spelling)
        # rtype not needed by generator; it accepts both call shapes
        generator.emit_deterministic_harness(fn.spelling, ptypes, edges, edge_out)
        generator.emit_libfuzzer_harness(fn.spelling, ptypes, edges, fuzz_out)

    print(f"autofuzz: clang targets -> {', '.join(names)}")

if __name__ == "__main__":
    run()
