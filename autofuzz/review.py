"""
Decide which findings need review instead of counting as firmware bugs.

A finding NEEDS REVIEW when it may be caused by the test, not the firmware:

  * the top stack frame is in test code: a generated harness (gen/), a
    generated stub (stubs/), a fake header (fake_include_dirs) or the
    AutoFuzz runtime (autofuzz/rt/);
  * it is a NULL-pointer crash, and the test program passed NULL for a pointer
    argument (a pointer parameter with no harness.setup entry whose type the
    test cannot create, e.g. void * or an opaque struct, gets NULL);
  * the test passed a zero-filled object for a pointer argument (a pointer
    parameter with no harness.setup entry), and the function read or wrote
    past that one object, or hit a NULL pointer although no argument was NULL
    (a NULL pointer inside the zero-filled struct).

The runner calls classify() on the output of each test program and writes
one line per such finding into the log:

  AUTOFUZZ: NEEDS REVIEW (<reason>): <the report line it is about>

The report line is the sanitizer SUMMARY line or the assert message, so
Tests/check_results.py (and later the report) can match them.
"""
import re
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

MARKER = "AUTOFUZZ: NEEDS REVIEW"
NULL_ARGS_TAG = "AUTOFUZZ-NULL-ARGS:"   # written by the generator into a harness
ZERO_ARGS_TAG = "AUTOFUZZ-ZERO-ARGS:"   # the same for zero-filled objects
ZERO_VAR_PREFIX = "afz_zero_"           # name of a zero-filled object in a harness

_ASAN_ERROR = re.compile(r"^==\d+==\s*ERROR: (AddressSanitizer|libFuzzer): (.*)$")
_UBSAN_ERROR = re.compile(r"^(\S+?):(\d+):(?:\d+:)? runtime error: (.*)$")
_FRAME = re.compile(r"^\s*#\d+ 0x[0-9a-f]+ in \S+ (/\S+?\.(?:c|h|cc|cpp|inc)):(\d+)")
_SUMMARY = re.compile(r"^SUMMARY: (AddressSanitizer|UndefinedBehaviorSanitizer|libFuzzer): ")
# glibc: "<prog>: <file>:<line>: <function or its full signature>: Assertion `<expr>' failed."
ASSERT_LINE = re.compile(r"^\S+: (\S+?\.(?:c|h)):(\d+): (.+?): Assertion `.*' failed\.$")
_ZERO_PAGE = re.compile(r"(?:unknown address|address) (0x[0-9a-f]+)")


def _tagged(harness_src: str, tag: str) -> str:
    for line in harness_src.splitlines():
        if tag in line:
            return line.split(tag, 1)[1].replace("*/", "").split(".")[0].strip()
    return ""


def null_args(harness_src: str) -> str:
    """The NULL arguments listed in a generated harness ('' if none)."""
    return _tagged(harness_src, NULL_ARGS_TAG)


def zero_args(harness_src: str) -> str:
    """The zero-filled arguments listed in a generated harness ('' if none)."""
    return _tagged(harness_src, ZERO_ARGS_TAG)


def _in(path: str, folders: Sequence[Path]) -> Optional[Path]:
    p = Path(path).resolve()
    for f in folders:
        try:
            p.relative_to(f)
            return f
        except ValueError:
            continue
    return None


class _Report:
    def __init__(self):
        self.top: Optional[str] = None     # file of the first frame with a source file
        self.null = False                  # a NULL-pointer access
        self.zero_obj = False              # ASan: the bad address is in a zero-filled object
        self.key: Optional[str] = None     # the SUMMARY or assert line


def _reports(text: str) -> List[_Report]:
    out: List[_Report] = []
    cur: Optional[_Report] = None
    for line in text.splitlines():
        m = ASSERT_LINE.match(line)
        if m:
            r = _Report()
            r.top, r.key = m.group(1), line
            out.append(r)
            continue
        m = _ASAN_ERROR.match(line)
        if m:
            cur = _Report()
            msg = m.group(2)
            z = _ZERO_PAGE.search(msg)
            if "SEGV" in msg and z and int(z.group(1), 16) < 0x1000:
                cur.null = True
            continue
        m = _UBSAN_ERROR.match(line)
        if m and cur is None:
            cur = _Report()
            cur.top = m.group(1)
            cur.null = "null pointer" in m.group(3)
            continue
        if cur is None:
            continue
        if "Hint: address points to the zero page" in line:
            cur.null = True
        # ASan stack report: "    [32, 36) 'afz_zero_a0' (line 20) <== Memory access at offset 36 overflows this variable"
        if f"'{ZERO_VAR_PREFIX}" in line and "<== Memory access" in line:
            cur.zero_obj = True
        m = _FRAME.match(line)
        if m and cur.top is None:
            cur.top = m.group(1)
            continue
        if _SUMMARY.match(line):
            cur.key = line.rstrip()
            out.append(cur)
            cur = None
    return out


def classify(text: str, harness_null_args: str, test_dirs: Sequence[Tuple[str, Path]],
             harness_zero_args: str = "") -> List[Tuple[str, str]]:
    """[(reason, report line)] for every finding in `text` that needs review.
    test_dirs: [(what it is, folder)], e.g. ("generated harness", out/gen)."""
    folders = [d.resolve() for _, d in test_dirs]
    names = {d.resolve(): what for what, d in test_dirs}
    result: List[Tuple[str, str]] = []
    for r in _reports(text):
        if r.key is None:
            continue
        where = _in(r.top, folders) if r.top else None
        if where is not None:
            result.append((f"top frame in {names[where]}: {Path(r.top).name}", r.key))
        elif r.null and harness_null_args:
            result.append((f"NULL argument: the test passed NULL for {harness_null_args}", r.key))
        elif harness_zero_args and (r.zero_obj or r.null):
            result.append((f"zero-filled argument: the test passed a zero-filled object for "
                           f"{harness_zero_args}; add a harness.setup entry for its type", r.key))
    return result
