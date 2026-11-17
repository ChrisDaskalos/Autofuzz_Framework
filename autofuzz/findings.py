"""
Read findings from test output (sanitizers, CMocka, libFuzzer, assert).

Used by the report (report.py) and by Tests/check_results.py, so both read
the logs the same way.

A *finding* is one short, compiler-independent text, for example

    UBSAN signed-integer-overflow protocol.c:159
    ASAN global-buffer-overflow ringbuf.c:34 in ringbuf_push
    ASSERT servo.c:40 in Servo_Ramp
    FAILED test_servo_command_zero_step          (a CMocka test that failed)
    LIBFUZZER deadly signal                      (only if nothing else explains it)
    REVIEW (NULL argument) <one of the above>    (caused by the test, see review.py)
    SKIPPED <function> (<file>:<line>): <reason>
"""
import re
from typing import Dict, Iterable, List, Optional, Set

HEADER = re.compile(r"^=== (?:TEST|EDGE|FUZZ): (?:\./)?(\S+)(?: \(\d+s\))? ===")
FAILED = re.compile(r"^\[  FAILED  \] (\w+)\s*$")
SUMMARY = re.compile(r"^SUMMARY: (AddressSanitizer|UndefinedBehaviorSanitizer|libFuzzer): (.*)$")
# glibc prints the function name or its full signature: "void f(int)"
ASSERT = re.compile(r"^\S+: (?:\S*/)?([\w.+-]+\.(?:c|h)):(\d+): (.+?): Assertion `.*' failed\.$")
# Written by the runner (review.py) after a report that may be caused by the
# test itself. The finding is then "REVIEW (<reason>) <finding>".
REVIEW = re.compile(r"^AUTOFUZZ: NEEDS REVIEW \((.*?)(?::.*)?\): (.*)$")
LOCATION = re.compile(r"([\w.+-]+\.(?:c|h|cc|cpp|inc)):(\d+)")


def finding_from_summary(tool: str, rest: str) -> str:
    """Turn a sanitizer SUMMARY line into a short, compiler-independent text."""
    rest = re.sub(r"\(BuildId: [0-9a-f]+\)", "", rest).strip()
    kind = rest.split()[0] if rest else "?"
    loc = LOCATION.search(rest)
    where = f"{loc.group(1)}:{loc.group(2)}" if loc else ""
    if tool == "UndefinedBehaviorSanitizer":
        return f"UBSAN {kind} {where}".strip()
    if tool == "libFuzzer":
        return f"LIBFUZZER {rest}"
    func = rest.rsplit(" in ", 1)[1].strip() if " in " in rest else ""
    return f"ASAN {kind} {where} in {func}".replace("  ", " ")


def finding_from_line(line: str) -> Optional[str]:
    """A SUMMARY or assert line -> finding text, or None."""
    m = SUMMARY.match(line)
    if m:
        return finding_from_summary(m.group(1), m.group(2))
    m = ASSERT.match(line)
    if m:
        func = re.search(r"(\w+)\s*\(", m.group(3))
        return f"ASSERT {m.group(1)}:{m.group(2)} in {func.group(1) if func else m.group(3)}"
    return None


def parse(lines: Iterable[str], program: Optional[str] = None) -> Dict[str, dict]:
    """
    Return {program: {"findings": set, "done": bool, "review": set}} for one log.
    A program starts at its "=== EDGE|FUZZ|TEST: <name> ===" header.
    "done" = libFuzzer printed "Done N runs" (the fuzzer finished normally).
    """
    progs: Dict[str, dict] = {}

    def cur() -> dict:
        return progs.setdefault(program, {"findings": set(), "done": False, "review": set()})

    for line in lines:
        line = line.rstrip("\n")
        m = HEADER.match(line)
        if m:
            program = m.group(1)
            cur()
            continue
        if program is None:
            continue
        if line.startswith("Done ") and " runs in " in line:
            cur()["done"] = True
        m = FAILED.match(line)
        if m:
            cur()["findings"].add(f"FAILED {m.group(1)}")
        m = REVIEW.match(line)
        if m:
            f = finding_from_line(m.group(2))
            if f:
                cur()["findings"].discard(f)
                cur()["review"].add(f)
                cur()["findings"].add(f"REVIEW ({m.group(1)}) {f}")
            continue
        f = finding_from_line(line)
        if f and f not in cur()["review"]:
            cur()["findings"].add(f)

    # "deadly signal" only repeats a sanitizer or assert report. Keep it only
    # when there is no such report (e.g. a plain abort or trap).
    for p in progs.values():
        if any(re.match(r"(REVIEW \(.*?\) )?(ASAN|UBSAN|ASSERT)", f) for f in p["findings"]):
            p["findings"] = {f for f in p["findings"]
                             if not re.fullmatch(r"(REVIEW \(.*?\) )?LIBFUZZER deadly signal", f)}
    return progs


# ---------------------------------------------------------------------------
# Baseline: the findings a project expects (known bugs it does not fix yet)
# ---------------------------------------------------------------------------
class Expected:
    """One baseline entry: <stage> <program> <finding regex>, maybe optional."""

    def __init__(self, stage: str, program: str, pattern: str, required: bool, where: str = ""):
        self.stage = stage
        self.program = program
        self.pattern = pattern
        self.regex = re.compile(pattern)
        self.required = required
        self.where = where        # "file:line" of the entry, for messages

    def matches(self, stage: str, program: str, finding: str) -> bool:
        return stage == self.stage and program == self.program and bool(self.regex.fullmatch(finding))

    def __str__(self) -> str:
        return f"{'maybe ' if not self.required else ''}{self.stage} {self.program} {self.pattern}"


def parse_expected(line: str, stages: Iterable[str], where: str = "") -> Optional[Expected]:
    """'[maybe] <stage> <program> <regex>' -> Expected; None for a blank or # line.
    Raises ValueError for a line it cannot read."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    required = True
    if line.startswith("maybe "):
        required = False
        line = line[len("maybe "):].strip()
    parts = line.split(None, 2)
    if len(parts) != 3 or parts[0] not in stages:
        raise ValueError(f"{where}: cannot read baseline line: {line}" if where else
                         f"cannot read baseline line: {line}")
    try:
        return Expected(parts[0], parts[1], parts[2], required, where)
    except re.error as e:
        raise ValueError(f"{where}: bad regular expression in baseline line: {line} ({e})")


def compare(found: Dict[str, Dict[str, Set[str]]], expected: List[Expected]):
    """
    found: {stage: {program: {finding, ...}}}.
    Returns (new, missing, used): findings matched by no entry as
    [(stage, program, finding)], required entries that matched nothing, and
    the indexes of the entries that matched.
    """
    used: Set[int] = set()
    new = []
    for stage in sorted(found):
        for prog in sorted(found[stage]):
            for f in sorted(found[stage][prog]):
                hit = [i for i, e in enumerate(expected) if e.matches(stage, prog, f)]
                if hit:
                    used.update(hit)
                else:
                    new.append((stage, prog, f))
    missing = [e for i, e in enumerate(expected) if e.required and i not in used]
    return new, missing, used
