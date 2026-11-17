# File: autofuzz/clang_helper.py
import os
import ctypes.util
import pathlib
import shutil
import subprocess
from typing import List                           # ← Python-3.8 typing
from clang import cindex


# --------------------------------------------------------------------------- #
# Locate a suitable libclang                                                  #
# --------------------------------------------------------------------------- #
def locate_libclang() -> str:
    """Return a usable libclang shared object (best-effort)."""
    # 1. Explicit environment variable
    if (p := os.getenv("CLANG_LIB")) and pathlib.Path(p).exists():
        return p

    # 2. Whatever `ldconfig` / system linker finds
    if (cand := ctypes.util.find_library("clang")):
        return cand

    # 3. Use `llvm-config --libdir`
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

    # 4. CI or fallback path
    return "/usr/lib/llvm-20/lib/libclang.so"


# --------------------------------------------------------------------------- #
# Configure libclang for clang.cindex                                         #
# --------------------------------------------------------------------------- #
def configure_clang() -> None:
    """Tell clang.cindex where its shared library lives."""
    cindex.Config.set_library_file(locate_libclang())


# --------------------------------------------------------------------------- #
# Parse a C file into an AST                                                  #
# --------------------------------------------------------------------------- #
def parse_source(path: str, args: List[str]) -> cindex.TranslationUnit:
    """
    Parse a C source file and return a clang TranslationUnit.
    Example args: ["-DUNIT_TEST", "-I<project-root>"]
    """
    idx = cindex.Index.create()
    return idx.parse(path, args=args)
