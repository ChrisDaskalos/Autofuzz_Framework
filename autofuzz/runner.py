# File: autofuzz/runner.py
"""
Check the tools, then generate, compile and run the tests of one project.

Everything goes into the output folder (output_dir in autofuzz.yaml,
default autofuzz-out/):

  gen/                  generated deterministic_edge_*.c and random_fuzz_*.c
  stubs/stubs.c         stubs for what the sources use but do not define
  build/edge, build/fuzz  object files of your sources
  bin/                  the test programs
  logs/edge.log         output of all edge tests
  logs/fuzz.log         output of all fuzzers
  crashes/              inputs that made a fuzzer crash
  corpus/<fuzzer>/      inputs each fuzzer keeps between runs

The project needs no Makefile: clang is called directly.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import Config, PACKAGE_DIR
from . import review

SUBDIRS = ("gen", "stubs", "build", "bin", "logs", "crashes", "corpus")

WARN_FLAGS = ["-Wall", "-Wextra", "-g", "-O0", "-fno-omit-frame-pointer"]
# Only for the generated tests: a function that harness.includes does not
# declare must stop the build (clang < 16 only warns and guesses `int f()`).
HARNESS_FLAGS = ["-Werror=implicit-function-declaration"]
SAN_EDGE = ["-fsanitize=address,undefined", "-fno-sanitize-recover=address"]
SAN_FUZZ = ["-fsanitize=address,undefined,integer", "-fno-sanitize-recover=all"]

RUN_ENV = {
    "CMOCKA_MESSAGE_OUTPUT": "STDOUT",
    "CMOCKA_COLOR": "on",
    "ASAN_OPTIONS": "detect_leaks=1:abort_on_error=1",
    "UBSAN_OPTIONS": "print_stacktrace=1:halt_on_error=1:report_error_type=1",
}

SUMMARY_RE = re.compile(r"^SUMMARY: |^\[  FAILED  \] \w+\s*$|: Assertion `.*' failed\.$")


def say(msg: str = "") -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# 1. Are the tools installed?
# ---------------------------------------------------------------------------
def _clang_major(cc: str) -> Optional[int]:
    try:
        out = subprocess.run([cc, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"clang version (\d+)", out)
    return int(m.group(1)) if m else None


def _compiles(cc: str, code: str, flags: List[str]) -> bool:
    with tempfile.TemporaryDirectory(prefix="autofuzz-check-") as tmp:
        src = Path(tmp) / "t.c"
        src.write_text(code)
        try:
            r = subprocess.run([cc, str(src)] + flags + ["-o", str(Path(tmp) / "t")],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        except (OSError, subprocess.SubprocessError):
            return False
        return r.returncode == 0


def check_tools(cc: str = "clang", need_fuzz: bool = True, need_compiler: bool = True) -> List[Tuple[str, str]]:
    """Return [(what is missing, exact command to install it)]; empty = all good."""
    missing: List[Tuple[str, str]] = []

    try:
        import yaml  # noqa: F401
    except ImportError:
        missing.append(("PyYAML (Python package)", "pip install PyYAML"))

    try:
        from clang import cindex
        cindex.Index.create()
    except Exception:
        missing.append(("libclang (Python package for the C parser)", "pip install libclang==18.1.1"))

    if not need_compiler:
        return missing
    if shutil.which(cc) is None:
        if cc == "clang":
            missing.append(("clang (C compiler)", "sudo apt install clang"))
        else:
            missing.append((f"{cc} (the C compiler set by 'compiler:' in autofuzz.yaml)",
                            f"install {cc}, or set 'compiler: clang' in autofuzz.yaml"))
        return missing  # the checks below need the compiler

    if not _compiles(cc, "#include <stdarg.h>\n#include <stddef.h>\n#include <setjmp.h>\n"
                         "#include <cmocka.h>\nint main(void){return 0;}\n", ["-lcmocka"]):
        missing.append(("CMocka (unit test library)", "sudo apt install libcmocka-dev"))

    sanitizers_ok = _compiles(cc, "int main(void){return 0;}\n", ["-fsanitize=address,undefined"])
    major = _clang_major(cc)
    # Ubuntu: LLVM 15+ has the runtimes in libclang-rt-N-dev, older in libclang-common-N-dev
    rt_pkg = f"libclang-rt-{major}-dev" if major and major >= 15 else f"libclang-common-{major}-dev"
    if major is None:
        # Not clang: gcc has no libFuzzer, and its sanitizer package names differ.
        fix = "sudo apt install clang   and set 'compiler: clang' in autofuzz.yaml"
        if not sanitizers_ok:
            missing.append((f"AddressSanitizer/UBSan support in {cc}", fix))
        elif need_fuzz:
            missing.append((f"libFuzzer ({cc} cannot build fuzzers, only clang can)", fix))
        return missing
    if not sanitizers_ok:
        missing.append((f"AddressSanitizer/UBSan runtime for {cc}", f"sudo apt install {rt_pkg}"))
    if need_fuzz and sanitizers_ok and not _compiles(
            cc, "#include <stdint.h>\n#include <stddef.h>\n"
                "int LLVMFuzzerTestOneInput(const uint8_t*d,size_t n){return 0;}\n",
            ["-fsanitize=fuzzer"]):
        missing.append((f"libFuzzer for {cc}", f"sudo apt install {rt_pkg}"))
    return missing


def report_missing(missing: List[Tuple[str, str]]) -> None:
    print("autofuzz: some tools are missing:", file=sys.stderr)
    for what, cmd in missing:
        print(f"  MISSING  {what}", file=sys.stderr)
        print(f"           install:  {cmd}", file=sys.stderr)
    print("Install them and run the command again. (docs/INSTALL.md has the full list.)", file=sys.stderr)


# ---------------------------------------------------------------------------
# 2. Generate
# ---------------------------------------------------------------------------
class Layout:
    def __init__(self, out: Path):
        self.out = out
        self.gen = out / "gen"
        self.stubs = out / "stubs"
        self.obj_edge = out / "build" / "edge"
        self.obj_fuzz = out / "build" / "fuzz"
        self.bin = out / "bin"
        self.logs = out / "logs"
        self.crashes = out / "crashes"
        self.corpus = out / "corpus"


def test_dirs(cfg: Config, L: "Layout") -> List[Tuple[str, Path]]:
    """Folders with test code: a finding whose top frame is here needs review."""
    dirs = [("generated harness", L.gen), ("generated stub", L.stubs), ("AutoFuzz runtime", PACKAGE_DIR / "rt")]
    return dirs + [("fake header", d) for d in cfg.fake_include_dirs]


def generate(cfg: Config, out: Path) -> List[str]:
    from .main import generate as gen  # imports libclang; only after check_tools
    from . import stubgen
    L = Layout(out)
    names = gen(cfg, L.gen)
    stubgen.generate(cfg, L.stubs)
    return names


# ---------------------------------------------------------------------------
# 3. Compile
# ---------------------------------------------------------------------------
class BuildError(Exception):
    pass


def _cc(cmd: List[str]) -> Tuple[bool, str]:
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    return r.returncode == 0, r.stdout


def _first_error(text: str) -> str:
    for line in text.splitlines():
        if "error" in line:
            return line.strip()
    return text.strip().splitlines()[0] if text.strip() else "(no output)"


def build(cfg: Config, out: Path, targets: List[str]) -> Dict[str, List[str]]:
    """
    Compile the sources and link one edge test + one fuzzer per target.
    Returns {"edge": [program names], "fuzz": [...], "skipped": [...]}.
    A source that does not compile stops the build (BuildError).
    A harness that does not compile is skipped with a message.
    """
    L = Layout(out)
    common = WARN_FLAGS + cfg.clang_args() + [f"-I{PACKAGE_DIR / 'rt'}"]
    from .main import read_skipped
    result: Dict[str, List[str]] = {"edge": [], "fuzz": [], "skipped": read_skipped(L.gen)}
    objs: Dict[str, List[str]] = {"edge": [], "fuzz": []}
    for kind, odir, san in (("edge", L.obj_edge, SAN_EDGE), ("fuzz", L.obj_fuzz, SAN_FUZZ)):
        odir.mkdir(parents=True, exist_ok=True)
        for i, src in enumerate(cfg.sources):
            obj = odir / f"{i:02d}_{src.stem}.o"
            say(f"  CC ({kind})  {src.name}")
            ok, log = _cc([cfg.compiler] + common + san + ["-c", str(src), "-o", str(obj)])
            if not ok:
                raise BuildError(f"could not compile {src}:\n{log}")
            objs[kind].append(str(obj))
        stubs = L.stubs / "stubs.c"
        if stubs.is_file():
            obj = odir / "zz_autofuzz_stubs.o"
            say(f"  CC ({kind})  stubs.c")
            ok, log = _cc([cfg.compiler] + common + san + ["-c", str(stubs), "-o", str(obj)])
            if not ok:
                raise BuildError(f"could not compile the generated stubs {stubs}:\n{log}")
            objs[kind].append(str(obj))

    L.bin.mkdir(parents=True, exist_ok=True)
    for name in targets:
        for kind, prefix, san, link in (
                ("edge", "deterministic_edge_", SAN_EDGE, ["-lcmocka"]),
                ("fuzz", "random_fuzz_", SAN_FUZZ, ["-fsanitize=fuzzer"])):
            prog = prefix + name
            say(f"  LD ({kind})  {prog}")
            ok, log = _cc([cfg.compiler] + common + san + HARNESS_FLAGS + [str(L.gen / f"{prog}.c")]
                          + objs[kind] + link + ["-o", str(L.bin / prog)])
            if ok:
                result[kind].append(prog)
            else:
                msg = f"{prog}: could not compile: {_first_error(log)}"
                say(f"  SKIPPED: {msg}")
                result["skipped"].append(msg)
    return result


# ---------------------------------------------------------------------------
# 4. Run
# ---------------------------------------------------------------------------
def _run_logged(cmd: List[str], cwd: Path, log, header: str, timeout: int,
                review_ctx: Optional[Tuple[str, List[Tuple[str, Path]], str]] = None) -> Tuple[int, List[str]]:
    env = dict(os.environ)
    env.update(RUN_ENV)
    log.write(f"\n{header}\n")
    log.flush()
    try:
        r = subprocess.run(cmd, cwd=str(cwd), env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, universal_newlines=True,
                           errors="replace", timeout=timeout)
        text, rc = r.stdout, r.returncode
    except subprocess.TimeoutExpired as e:
        text = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        text += f"\nautofuzz: TIMEOUT after {timeout} s\n"
        rc = 124
    log.write(text)
    lines = [ln for ln in text.splitlines() if SUMMARY_RE.search(ln) and not ln.startswith("[  FAILED  ] tests:")]
    if review_ctx is not None:
        for reason, key in review.classify(text, review_ctx[0], review_ctx[1], review_ctx[2]):
            marker = f"{review.MARKER} ({reason}): {key}"
            log.write(marker + "\n")
            lines.append(marker)
    log.flush()
    return rc, lines


def _review_ctx(L: Layout, prog: str, dirs: List[Tuple[str, Path]]):
    src = L.gen / f"{prog}.c"
    text = src.read_text(encoding="utf-8") if src.is_file() else ""
    return (review.null_args(text), dirs, review.zero_args(text))


def run_edge(L: Layout, progs: List[str], dirs: List[Tuple[str, Path]]) -> int:
    L.logs.mkdir(parents=True, exist_ok=True)
    found = 0
    with open(L.logs / "edge.log", "w") as log:
        for prog in sorted(progs):
            rc, summary = _run_logged([str(L.bin / prog)], L.out, log, f"=== EDGE: {prog} ===", 300,
                                      _review_ctx(L, prog, dirs))
            say(f"=== EDGE: {prog} === {'ok' if rc == 0 else 'FOUND SOMETHING'}")
            for line in summary:
                say(f"    {line}")
            found += rc != 0
    return found


def run_fuzz(L: Layout, progs: List[str], seconds: int, dirs: List[Tuple[str, Path]]) -> int:
    L.logs.mkdir(parents=True, exist_ok=True)
    L.crashes.mkdir(parents=True, exist_ok=True)
    found = 0
    with open(L.logs / "fuzz.log", "w") as log:
        for prog in sorted(progs):
            corpus = L.corpus / prog
            corpus.mkdir(parents=True, exist_ok=True)
            cmd = [str(L.bin / prog), "-use_value_profile=1", "-artifact_prefix=crashes/",
                   f"-max_total_time={seconds}", str(corpus.relative_to(L.out))]
            rc, summary = _run_logged(cmd, L.out, log, f"=== FUZZ: {prog} ===", seconds + 120,
                                      _review_ctx(L, prog, dirs))
            say(f"=== FUZZ: {prog} ({seconds}s) === {'ok' if rc == 0 else 'FOUND SOMETHING'}")
            for line in summary:
                say(f"    {line}")
            found += rc != 0
    return found


def clean(out: Path) -> List[Path]:
    """Remove only the folders AutoFuzz creates. Never the whole output_dir
    unless it is empty afterwards."""
    removed = []
    for sub in SUBDIRS:
        p = out / sub
        if p.exists():
            shutil.rmtree(p)
            removed.append(p)
    try:
        out.rmdir()
    except OSError:
        pass
    return removed


def reset_fuzz_state(out: Path) -> None:
    """Forget old corpus, crashes and logs, so a run starts the same every time."""
    for sub in ("logs", "crashes", "corpus"):
        if (out / sub).exists():
            shutil.rmtree(out / sub)
