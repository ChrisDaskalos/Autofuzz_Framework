"""
The AutoFuzz report: every finding in plain words, with what you need to
repeat it.

After `autofuzz run`, this module reads <output_dir>/logs/{edge,fuzz}.log,
gen/skipped.txt and the crash files, and writes

  <output_dir>/report.md     for people
  <output_dir>/report.json   for `autofuzz repro <id>`

Each finding has
  * an id (F1, F2, ...), the same order every time: firmware bugs first,
    then needs review, then skipped; inside each by file and line;
  * a status: FIRMWARE BUG, NEEDS REVIEW or SKIPPED;
  * one plain sentence, the sanitizer message and the line of code;
  * file, line and function;
  * the input: the arguments of the edge test, or the crash file of the
    fuzzer (as hex and as printable text);
  * the command to repeat it.

The same bug found by several programs (edge test and fuzzer) is shown once:
findings are merged by (status, kind, file, line).
"""
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .findings import (ASSERT, HEADER, LOCATION, REVIEW, SUMMARY, Expected,
                       finding_from_line)

REPORT_MD = "report.md"
REPORT_JSON = "report.json"
STATUS_ORDER = ("FIRMWARE BUG", "NEEDS REVIEW", "SKIPPED")

_UBSAN_MSG = re.compile(r"^(\S+?\.(?:c|h|cc|cpp|inc)):(\d+):(?:\d+:)? runtime error: (.*)$")
_ASAN_MSG = re.compile(r"^==\d+==\s*ERROR: AddressSanitizer: (\S+)(.*)$")
_ACCESS = re.compile(r"^(READ|WRITE) of size (\d+)")
_LOCATED = re.compile(r"is located .*?(?:of|in) (?:global variable|stack of thread)? ?'?([\w.]*)'?")
_FRAME = re.compile(r"^\s*#\d+ 0x[0-9a-f]+ in (\S+) (/\S+?\.(?:c|h|cc|cpp|inc)):(\d+)")
_RUN = re.compile(r"^\[ RUN      \] (\w+)")
_CRASH = re.compile(r"Test unit written to (\S+)")

# One plain sentence per kind of finding.
PLAIN = {
    "signed-integer-overflow": "Signed integer overflow: the result of an int calculation is too big "
                               "or too small for its type. In C this is undefined behaviour.",
    "unsigned-integer-overflow": "Unsigned integer overflow: the result wrapped around. This is allowed "
                                 "in C, but often not intended.",
    "integer-divide-by-zero": "Division by zero.",
    "null-pointer-use": "The code reads or writes through a NULL pointer.",
    "nullptr-with-offset": "The code does pointer arithmetic on a NULL pointer.",
    "invalid-null-argument": "A NULL pointer is passed where it is not allowed.",
    "shift-exponent": "A bit shift by a negative amount or by too many bits.",
    "shift-base": "A left shift of a negative value, or one whose result does not fit.",
    "implicit-signed-integer-truncation": "An implicit conversion cuts off part of a value.",
    "implicit-unsigned-integer-truncation": "An implicit conversion cuts off part of a value.",
    "implicit-integer-sign-change": "An implicit conversion changes the sign of a value.",
    "out-of-bounds-index": "An array index is outside the array.",
    "undefined-behavior": "Undefined behaviour in C (see the message).",
    "stack-buffer-overflow": "Buffer overflow on the stack: the code reads or writes past the end of a local variable.",
    "stack-buffer-underflow": "Buffer underflow on the stack: the code reads or writes before the start of a local variable.",
    "global-buffer-overflow": "Buffer overflow in a global variable: the code reads or writes past its end.",
    "heap-buffer-overflow": "Buffer overflow on the heap: the code reads or writes past the end of a malloc'ed block.",
    "dynamic-stack-buffer-overflow": "Buffer overflow of a variable-length array or alloca block.",
    "heap-use-after-free": "Use after free: the code uses memory that was already freed.",
    "double-free": "The same memory is freed twice.",
    "stack-use-after-return": "The code uses a local variable of a function that has already returned.",
    "stack-overflow": "Stack overflow: too deep recursion or a too large local variable.",
    "SEGV": "Crash: the code accessed an invalid memory address (segmentation fault).",
    "detected": "Memory leak: memory is allocated and never freed.",
    "ASSERT": "An assert() failed: the code reached a state that its author said must never happen.",
    "deadly": "The program crashed (a signal such as abort), without a sanitizer report.",
    "timeout": "Timeout: the function did not return in time (maybe an endless loop).",
    "out-of-memory": "The program used too much memory.",
    "FAILED": "A CMocka check in the test failed.",
}
REVIEW_TEXT = ("This is probably caused by the test, not by your code ({reason}). "
               "Check the test first (docs/CONFIG.md, 'Needs review').")


class Occurrence:
    """One place where a finding was seen: one program, one input."""

    def __init__(self, stage: str, program: str):
        self.stage = stage            # "edge" or "fuzz"
        self.program = program
        self.text = ""                # the finding text (findings.py), e.g. "UBSAN signed-integer-overflow protocol.c:159"
        self.message = ""             # sanitizer message
        self.function = ""
        self.path = ""                # full path of the source file
        self.frame_line = 0           # line of the first stack frame in a source file
        self.top_function = ""        # function named in the SUMMARY (may be libc, e.g. strtok)
        self.test = ""                # CMocka test (edge)
        self.crash = ""               # crash file relative to output_dir (fuzz)
        self.review = ""              # needs-review reason, or ""
        self.known = False            # matched by the baseline


class Finding:
    def __init__(self, status: str, kind: str, file: str, line: int):
        self.id = ""
        self.status = status
        self.kind = kind
        self.file = file
        self.line = line
        self.occ: List[Occurrence] = []

    @property
    def first(self) -> Occurrence:
        # an edge test repeats the same way every time: prefer it
        edge = [o for o in self.occ if o.stage == "edge"]
        return (edge or self.occ)[0]

    @property
    def known(self) -> bool:
        return all(o.known for o in self.occ)


# ---------------------------------------------------------------------------
# Reading the logs
# ---------------------------------------------------------------------------
def _occurrences(lines: Sequence[str], stage: str) -> List[Occurrence]:
    """Every sanitizer report, assert and libFuzzer crash in one log."""
    out: List[Occurrence] = []
    prog = None
    test = ""
    pending: Optional[Occurrence] = None      # message seen, SUMMARY not yet
    last: Optional[Occurrence] = None         # the last finished one in this program
    for raw in lines:
        line = raw.rstrip("\n")
        m = HEADER.match(line)
        if m:
            prog, test, pending, last = m.group(1), "", None, None
            continue
        if prog is None:
            continue
        m = _RUN.match(line)
        if m:
            test = m.group(1)
            continue
        m = REVIEW.match(line)
        if m:
            text = finding_from_line(m.group(2))
            for o in out:
                if o.program == prog and o.text == text:
                    o.review = m.group(1)
            continue
        m = _CRASH.search(line)
        if m and last is not None and not last.crash:
            last.crash = m.group(1)
            continue
        m = _UBSAN_MSG.match(line)
        if m and pending is None:
            pending = Occurrence(stage, prog)
            pending.path, pending.message = m.group(1), m.group(3)
            continue
        m = _ASAN_MSG.match(line)
        if m and pending is None:
            pending = Occurrence(stage, prog)
            pending.message = m.group(1).rstrip(":")
            continue
        if pending is not None:
            m = _ACCESS.match(line)
            if m:
                pending.message += f": {m.group(1)} of {m.group(2)} byte(s)"
            m = _FRAME.match(line)
            if m and not pending.function:
                pending.function, pending.path, pending.frame_line = m.group(1), m.group(2), int(m.group(3))
            if " is located " in line and "in stack of thread" not in line:
                # "0x... is located 0 bytes to the right of global variable 'g' defined in '...c:12:16' (0x...) of size 8"
                where = line.split(" is located ", 1)[1].split(" (0x")[0]
                where = re.sub(r" defined in '[^']*'", "", where)
                pending.message += f" ({where})"
            if "<== Memory access" in line:
                # "    [32, 36) 'afz_zero_a0' (line 20) <== Memory access at offset 36 overflows this variable"
                var = re.search(r"'([^']+)'", line)
                what = line.split("<== ", 1)[1].strip()
                pending.message += f" (variable '{var.group(1) if var else '?'}': {what})"
        m = ASSERT.match(line)
        if m:
            o = Occurrence(stage, prog)
            o.text = finding_from_line(line) or ""
            o.message = line.split(": ", 1)[1] if ": " in line else line
            o.path, o.test = m.group(1), test
            fn = re.search(r"(\w+)\s*\(", m.group(3))
            o.function = fn.group(1) if fn else m.group(3)
            out.append(o)
            last = o
            continue
        if SUMMARY.match(line):
            text = finding_from_line(line) or ""
            if text == "LIBFUZZER deadly signal" and last is not None:
                continue        # only repeats the report before it
            o = pending or Occurrence(stage, prog)
            o.text, o.test = text, test
            inside = re.search(r" in (\w+)\s*$", line)
            if inside and o.function and inside.group(1) != o.function:
                o.top_function = inside.group(1)    # e.g. strtok, called from o.function
            if not o.message:
                o.message = SUMMARY.match(line).group(2)
            out.append(o)
            last, pending = o, None
    return out


def _kind_file_line(o: Occurrence) -> Tuple[str, str, int]:
    words = o.text.split()
    kind = words[0] if words and words[0] in ("ASSERT", "FAILED") else (words[1] if len(words) > 1 else "?")
    if words and words[0] == "LIBFUZZER":
        kind = words[1] if len(words) > 1 else "?"
    loc = LOCATION.search(o.text)
    if loc:
        return kind, loc.group(1), int(loc.group(2))
    if o.path:   # no location in the SUMMARY (crash inside libc): first frame in a source file
        return kind, Path(o.path).name, o.frame_line
    return kind, "", 0


def _skipped(gen: Path, extra: Sequence[str]) -> List[Finding]:
    out = []
    lines = []
    f = gen / "skipped.txt"
    if f.is_file():
        lines += [ln.strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
    lines += [s for s in extra if "could not compile" in s]
    for ln in lines:
        m = re.match(r"(\w+) \(([^:()]+):(\d+)\): (.*)", ln)
        if m:
            fd = Finding("SKIPPED", "skipped", Path(m.group(2)).name, int(m.group(3)))
            o = Occurrence("skipped", m.group(1))
            o.function, o.message, o.text = m.group(1), m.group(4), f"SKIPPED {ln}"
        else:   # "<program>: could not compile: <error>"
            prog, _, err = ln.partition(": ")
            fd = Finding("SKIPPED", "not-compiled", "", 0)
            o = Occurrence("skipped", prog)
            o.message, o.text = err, f"SKIPPED {ln}"
        fd.occ.append(o)
        out.append(fd)
    return out


def collect(out_dir: Path, baseline: Sequence[Expected] = (), build_skipped: Sequence[str] = ()) -> List[Finding]:
    """All findings of the last run in out_dir, merged and numbered."""
    occ: List[Occurrence] = []
    for stage in ("edge", "fuzz"):
        log = out_dir / "logs" / f"{stage}.log"
        if log.is_file():
            occ += _occurrences(log.read_text(errors="replace").splitlines(), stage)
    merged: Dict[Tuple[str, str, str, int], Finding] = {}
    for o in occ:
        if not o.text:
            continue
        status = "NEEDS REVIEW" if o.review else "FIRMWARE BUG"
        kind, file, line = _kind_file_line(o)
        key = (status, kind, file, line)
        if key not in merged:
            merged[key] = Finding(status, kind, file, line)
        merged[key].occ.append(o)
    findings = list(merged.values()) + _skipped(out_dir / "gen", build_skipped)
    for f in findings:
        for o in f.occ:
            text = f"REVIEW ({o.review}) {o.text}" if o.review else o.text
            o.known = any(e.matches(o.stage, o.program if o.stage != "skipped" else o.function or o.program, text)
                          for e in baseline)
    findings.sort(key=lambda f: (STATUS_ORDER.index(f.status), f.file, f.line, f.kind,
                                 f.occ[0].program))
    for i, f in enumerate(findings, 1):
        f.id = f"F{i}"
    return findings


# ---------------------------------------------------------------------------
# Inputs and repeat commands
# ---------------------------------------------------------------------------
def _edge_input(gen: Path, o: Occurrence) -> List[str]:
    """The lines of the edge test function that set up the arguments and call."""
    src = gen / f"{o.program}.c"
    if not o.test or not src.is_file():
        return []
    lines = src.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.startswith(f"static void {o.test}("))
    except StopIteration:
        return []
    body = []
    for ln in lines[start + 1:]:
        if ln.startswith("}"):
            break
        s = ln.strip()
        if not s or s.startswith("/*") or s == "(void)state;":
            continue
        body.append(s)
    return body


def _bytes_text(data: bytes, limit: int = 96) -> Tuple[str, str]:
    part = data[:limit]
    hexs = " ".join(f"{b:02x}" for b in part) + (" ..." if len(data) > limit else "")
    text = "".join(chr(b) if 32 <= b < 127 and b != 92 else
                   {9: "\\t", 10: "\\n", 13: "\\r", 92: "\\\\"}.get(b, f"\\x{b:02x}") for b in part)
    return hexs, text + (" ..." if len(data) > limit else "")


def repeat_command(o: Occurrence) -> List[str]:
    """The command (run in output_dir) that repeats this occurrence."""
    if o.stage == "fuzz" and o.crash:
        return [f"./bin/{o.program}", o.crash]
    if o.stage in ("edge", "fuzz"):
        return [f"./bin/{o.program}"]
    return []


def _repeats(out_dir: Path, o: Occurrence) -> bool:
    """Run the fuzzer once with its crash file: does it fail again?"""
    from .runner import RUN_ENV
    env = dict(os.environ)
    env.update(RUN_ENV)
    try:
        r = subprocess.run(repeat_command(o), cwd=str(out_dir), env=env, timeout=60,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode != 0


def _code_line(o: Occurrence, line: int) -> str:
    try:
        return Path(o.path).read_text(errors="replace").splitlines()[line - 1].strip()
    except (OSError, IndexError, ValueError):
        return ""


def _sentence(f: Finding) -> str:
    s = PLAIN.get(f.kind, f"{f.kind} (see the message).")
    if f.status == "NEEDS REVIEW":
        s += " " + REVIEW_TEXT.format(reason=f.first.review)
    return s


def _as_dict(f: Finding, out_dir: Path) -> dict:
    o = f.first
    d = {
        "id": f.id, "status": f.status, "kind": f.kind, "known": f.known,
        "file": f.file, "line": f.line, "function": o.function,
        "sentence": _sentence(f) if f.status != "SKIPPED" else o.message,
        "inside": o.top_function,
        "message": o.message, "code": _code_line(o, f.line) if f.line else "",
        "found_by": [f"{x.stage} {x.program}" for x in f.occ],
        "test": o.test, "arguments": [], "input_file": "", "input_program": "", "input_repeats": False,
        "input_hex": "", "input_text": "", "input_size": 0,
        "command": repeat_command(o), "cwd": str(out_dir),
    }
    if o.stage == "edge":
        d["arguments"] = _edge_input(out_dir / "gen", o)
    # A fuzzer input. Prefer one that crashes again when it is run alone: a
    # function that keeps state between calls (a global buffer, ...) may need
    # the inputs the fuzzer tried before it.
    crashes = [x for x in f.occ if x.crash]
    crash = next((x for x in crashes if _repeats(out_dir, x)), None)
    d["input_repeats"] = crash is not None
    crash = crash or (crashes[0] if crashes else None)
    if crash is not None:
        p = out_dir / crash.crash
        d["input_file"] = crash.crash
        d["input_program"] = crash.program
        if o.stage != "edge":
            d["command"] = repeat_command(crash)
        if p.is_file():
            data = p.read_bytes()
            d["input_size"] = len(data)
            d["input_hex"], d["input_text"] = _bytes_text(data)
    return d


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------
def _md(items: List[dict], out_dir: Path, config: str, missing: Sequence[Expected]) -> str:
    n = {s: sum(1 for i in items if i["status"] == s) for s in STATUS_ORDER}
    new = [i for i in items if i["status"] == "FIRMWARE BUG" and not i["known"]]
    cfg_opt = f" --config {config}" if config else ""
    out = ["# AutoFuzz report", "",
           f"- **{n['FIRMWARE BUG']} firmware bug(s)**"
           + (f", {len(new)} of them new (not in the baseline)" if new else
              (", all in the baseline" if n["FIRMWARE BUG"] else "")),
           f"- {n['NEEDS REVIEW']} need review (probably caused by the test)",
           f"- {n['SKIPPED']} skipped (cannot run on a PC, or did not compile)", ""]
    if missing:
        out += ["Baseline entries that were **not** found (fixed, or not reached this time):", ""]
        out += [f"- `{e}`" for e in missing] + [""]
    out += ["Repeat a finding: `autofuzz repro <id>" + cfg_opt + "`. "
            f"The commands below run in `{out_dir}`.", ""]
    for i in items:
        where = f"{i['file']}:{i['line']}" if i["line"] else i["file"]
        title = f"## {i['id']}  {i['status']}"
        if i["status"] == "FIRMWARE BUG":
            title += "  (known, in the baseline)" if i["known"] else "  (NEW)"
        out += [title, ""]
        if i["status"] == "SKIPPED":
            out += [f"- **Function:** `{i['function'] or i['found_by'][0].split(' ', 1)[1]}`"
                    + (f" in `{where}`" if where else ""),
                    f"- **Why:** {i['message']}", ""]
            continue
        out += [i["sentence"], "",
                f"- **Where:** `{where}`" + (f" in `{i['function']}`" if i["function"] else "")
                + (f" (inside `{i['inside']}`, called from there)" if i.get("inside") else ""),
                f"- **Message:** {i['message']}"]
        if i["code"]:
            out.append(f"- **Code:** `{i['code']}`")
        out.append("- **Found by:** " + ", ".join(f"`{x}`" for x in i["found_by"]))
        if i["arguments"]:
            out += [f"- **Input** (edge test `{i['test']}`):", "", "  ```c"]
            out += [f"  {a}" for a in i["arguments"]] + ["  ```"]
        if i["input_file"]:
            out += [f"- **Input** of `{i['input_program']}` ({i['input_size']} bytes, `{i['input_file']}`):",
                    f"  - text: `{i['input_text']}`", f"  - hex: `{i['input_hex']}`"]
            if not i["input_repeats"]:
                out.append("  - This input does **not** crash again when it is run alone: the function "
                           "keeps state between calls, and the crash needed the inputs the fuzzer tried before.")
        if i["command"]:
            out += [f"- **Repeat:** `autofuzz repro {i['id']}{cfg_opt}`, or "
                    f"`cd {out_dir} && {' '.join(i['command'])}`"]
        out.append("")
    return "\n".join(out) + "\n"


def write(out_dir: Path, findings: List[Finding], config: str = "",
          missing: Sequence[Expected] = ()) -> List[dict]:
    items = [_as_dict(f, out_dir) for f in findings]
    (out_dir / REPORT_MD).write_text(_md(items, out_dir, config, missing), encoding="utf-8")
    (out_dir / REPORT_JSON).write_text(json.dumps({"findings": items}, indent=1) + "\n", encoding="utf-8")
    return items


def summary(items: List[dict], out_dir: Path, config: str = "") -> List[str]:
    """A few lines for the terminal."""
    cfg_opt = f" --config {config}" if config else ""
    n = {s: sum(1 for i in items if i["status"] == s) for s in STATUS_ORDER}
    lines = [f">>> Report: {n['FIRMWARE BUG']} firmware bug(s), {n['NEEDS REVIEW']} need review, "
             f"{n['SKIPPED']} skipped"]
    for i in items:
        if i["status"] == "SKIPPED":
            continue
        where = f"{i['file']}:{i['line']}" + (f" in {i['function']}" if i["function"] else "")
        tag = i["status"] + ("" if i["status"] != "FIRMWARE BUG" else (" (known)" if i["known"] else " (NEW)"))
        lines.append(f"    {i['id']:<4} {tag:<20} {where}: {i['sentence'].split('. ')[0].rstrip('.')}.")
        if i["command"]:
            lines.append(f"         repeat: autofuzz repro {i['id']}{cfg_opt}")
    lines.append(f"    Full report: {out_dir / REPORT_MD}")
    return lines


def missing(findings: List[Finding], baseline: Sequence[Expected]) -> List[Expected]:
    """Required baseline entries that no finding matched (a fixed bug?)."""
    seen = []
    for f in findings:
        for o in f.occ:
            seen.append((o.stage, o.function or o.program if o.stage == "skipped" else o.program,
                         f"REVIEW ({o.review}) {o.text}" if o.review else o.text))
    return [e for e in baseline if e.required and not any(e.matches(*x) for x in seen)]


def load(out_dir: Path) -> List[dict]:
    p = out_dir / REPORT_JSON
    if not p.is_file():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("findings", [])
