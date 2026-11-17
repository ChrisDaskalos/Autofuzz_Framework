# File: autofuzz/main.py
"""Scan the sources from the config and write the harness .c files."""
import os
import sys
import re
import shutil
from pathlib import Path
from typing import List, Tuple

from clang import cindex

# Optional: tell the Python bindings which libclang to load.
#   CLANG_LIB=/path/to/libclang.so      (a file)
#   LIBCLANG_PATH=/usr/lib/llvm-18/lib  (a folder that contains libclang.so)
# If neither is set, the bindings find libclang on their own (the pip
# package "libclang" ships its own copy, see requirements.txt).
_clang_lib = os.getenv("CLANG_LIB") or os.getenv("LIBCLANG_PATH")
if _clang_lib and not cindex.Config.loaded:
    if os.path.isdir(_clang_lib):
        cindex.Config.set_library_path(_clang_lib)
    else:
        cindex.Config.set_library_file(_clang_lib)

from . import config as config_mod
from .config import Config
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

SKIPPED_FILE = "skipped.txt"   # in the gen folder: functions that cannot run on a PC


def _where(fn: cindex.Cursor, cfg: Config) -> str:
    """file:line, relative to the config folder (the same on every machine)."""
    f = Path(fn.location.file.name).resolve()
    try:
        name = f.relative_to(cfg.base_dir.resolve()).as_posix()
    except ValueError:
        name = os.path.relpath(str(f), str(cfg.base_dir.resolve())).replace(os.sep, "/")
    return f"{name}:{fn.location.line}"


def read_skipped(gen_dir: Path) -> List[str]:
    p = Path(gen_dir) / SKIPPED_FILE
    return p.read_text(encoding="utf-8").splitlines() if p.is_file() else []


# -------- main flow ----------
def generate(cfg: Config, out_dir: Path, quiet: bool = False) -> List[str]:
    """
    Write deterministic_edge_<fn>.c and random_fuzz_<fn>.c for every target
    function into `out_dir`. Returns the target names (sorted).
    Same config + same sources -> the same files, byte for byte.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in list(out_dir.glob("deterministic_edge_*.c")) + list(out_dir.glob("random_fuzz_*.c")) \
            + list(out_dir.glob(SKIPPED_FILE)):
        old.unlink()  # a function that was removed must not keep its old harness

    index = cindex.Index.create()
    found = {}   # name -> (param types, edges)
    excluded: List[str] = []
    skipped: List[str] = []   # "name (file:line): reason"
    for src in cfg.sources:
        try:
            tu = index.parse(str(src), args=cfg.clang_args())
        except cindex.TranslationUnitLoadError:
            tu = None
        targets = scanner.extract_targets(tu, src) if tu is not None else []
        if targets:
            for fn in targets:
                if not cfg.wants_function(fn.spelling):
                    excluded.append(fn.spelling)
                    continue
                reason = scanner.skip_reason(fn)
                if reason:
                    skipped.append(f"{fn.spelling} ({_where(fn, cfg)}): {reason}")
                    continue
                ptypes, pnames = _param_types_and_names(fn)
                found[fn.spelling] = (ptypes, scanner.scan_function(fn, ptypes, pnames, cfg))
            continue
        # libclang found nothing: regex fallback over the file + its header
        probe = [src, src.with_suffix(".h")]
        for name, ptypes in _regex_fallback(probe):
            if not cfg.wants_function(name):
                excluded.append(name)
                continue
            found[name] = (ptypes, [set() for _ in ptypes])  # empty -> defaults per type

    names = sorted(found)
    if skipped:
        (out_dir / SKIPPED_FILE).write_text("".join(s + "\n" for s in sorted(skipped)), encoding="utf-8")
    for name in names:
        ptypes, edges = found[name]
        generator.emit_edge_harness(name, ptypes, edges, out_dir, cfg)
        generator.emit_libfuzzer_harness(name, ptypes, out_dir, cfg)

    if not quiet:
        if names:
            print(f"autofuzz: targets -> {', '.join(names)}")
        else:
            print("autofuzz: no target functions found in 'sources'.", file=sys.stderr)
        for s in sorted(skipped):
            print(f"autofuzz: SKIPPED: {s}")
        if excluded:
            print(f"autofuzz: left out by functions.include/exclude -> {', '.join(sorted(set(excluded)))}")
    return names


def run() -> None:
    """Old entry point: python3 -m autofuzz.main [--config FILE] [--out DIR]."""
    import argparse
    ap = argparse.ArgumentParser(prog="python3 -m autofuzz.main")
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    try:
        cfg = config_mod.load(a.config)
    except config_mod.ConfigError as e:
        config_mod.die(e)
    generate(cfg, Path(a.out))


if __name__ == "__main__":
    run()
