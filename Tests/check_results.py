#!/usr/bin/env python3
"""
Compare the findings of `make test` with Tests/expected_findings.txt.

Reads:
  Tests/results/unit.log                       (hand-written tests, Tests/legacy_thesis)
  Tests/results/<prefix>edge.log, fuzz.log     (`autofuzz run` of each suite in SUITES,
                                                copied by Tests/run_suite.sh)
  Tests/results/<prefix>skipped.txt            (functions AutoFuzz skipped, per suite)
  Tests/fuzz_manual/out/<fuzzer>.log           (output of Tests/fuzz_manual)

Prints one line per stage, then as the very last line either
  "All results as expected"            (exit code 0)
or
  "UNEXPECTED: ..."                     (exit code 1)
"""
import re
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
RESULTS = TESTS / "results"
UNIT_DIR = TESTS / "legacy_thesis"
MANUAL_DIR = TESTS / "fuzz_manual"
MANUAL_FUZZERS = ["fuzz_protocol_session", "fuzz_protocol_cmd", "fuzz_uart_dma"]

# AutoFuzz suites: name -> (log prefix in Tests/results/, folder of its autofuzz.yaml).
# Stages: <prefix>edge and <prefix>fuzz; the "skipped" stage uses the suite name as program.
SUITES = {
    "legacy": ("", UNIT_DIR),
    "self": ("self-", TESTS / "autofuzz_selftest"),
}
STAGES = ["unit"]
for _prefix, _ in SUITES.values():
    STAGES += [f"{_prefix}edge", f"{_prefix}fuzz"]
STAGES += ["skipped", "manual"]

HEADER = re.compile(r"^=== (?:TEST|EDGE|FUZZ): (?:\./)?(\S+) ===")
FAILED = re.compile(r"^\[  FAILED  \] (\w+)\s*$")
SUMMARY = re.compile(r"^SUMMARY: (AddressSanitizer|UndefinedBehaviorSanitizer|libFuzzer): (.*)$")
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


def parse(lines, program=None):
    """Return {program: {"findings": set, "done": bool}} for one log."""
    progs = {}

    def cur():
        return progs.setdefault(program, {"findings": set(), "done": False})

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
        m = SUMMARY.match(line)
        if m:
            cur()["findings"].add(finding_from_summary(m.group(1), m.group(2)))

    # "deadly signal" only repeats a sanitizer report. Keep it only when
    # there is no sanitizer report (e.g. a plain abort or trap).
    for p in progs.values():
        sanitizer = [f for f in p["findings"] if f.startswith(("ASAN", "UBSAN"))]
        if sanitizer:
            p["findings"].discard("LIBFUZZER deadly signal")
    return progs


def read(path: Path):
    return path.read_text(errors="replace").splitlines() if path.exists() else []


def programs_that_must_run():
    need = {"unit": sorted(p.stem + ".elf" for p in UNIT_DIR.glob("test_*.c") if p.name != "test_common.c"),
            "manual": MANUAL_FUZZERS}
    for prefix, folder in SUITES.values():
        gen = folder / "autofuzz-out" / "gen"   # output_dir in its autofuzz.yaml
        need[f"{prefix}edge"] = sorted(p.stem for p in gen.glob("deterministic_edge_*.c"))
        need[f"{prefix}fuzz"] = sorted(p.stem for p in gen.glob("random_fuzz_*.c"))
    return need


def skipped_findings():
    """{suite: {"findings": {"SKIPPED <name> (<file>:<line>): <reason>"}}}"""
    out = {}
    for name, (prefix, _) in SUITES.items():
        lines = [ln for ln in read(RESULTS / f"{prefix}skipped.txt") if ln.strip()]
        if lines:
            out[name] = {"findings": {f"SKIPPED {ln.strip()}" for ln in lines}, "done": True}
    return out


def load_expected():
    expected = []
    for n, line in enumerate(read(TESTS / "expected_findings.txt"), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        required = True
        if line.startswith("maybe "):
            required = False
            line = line[len("maybe "):].strip()
        parts = line.split(None, 2)
        if len(parts) != 3 or parts[0] not in STAGES:
            sys.exit(f"expected_findings.txt:{n}: cannot read line: {line}")
        expected.append((parts[0], parts[1], re.compile(parts[2]), required))
    return expected


def main() -> int:
    actual = {s: parse(read(RESULTS / f"{s}.log")) for s in STAGES if s not in ("skipped", "manual")}
    actual["skipped"] = skipped_findings()
    actual["manual"] = {}
    for name in MANUAL_FUZZERS:
        actual["manual"].update(parse(read(MANUAL_DIR / "out" / f"{name}.log"), program=name))

    expected = load_expected()
    problems = []

    # 1. Did every program run (and every fuzzer finish or report something)?
    for stage, names in programs_that_must_run().items():
        for name in names:
            p = actual[stage].get(name)
            if p is None:
                problems.append(f"did not run: {stage} {name}")
            elif (stage.endswith("fuzz") or stage == "manual") and not p["done"] and not p["findings"]:
                problems.append(f"did not finish: {stage} {name}")

    # 2. New findings, and expected findings that are missing.
    used = set()
    counts = {s: [0, 0] for s in STAGES}  # [findings, unexpected]
    for stage in STAGES:
        for prog, p in sorted(actual[stage].items()):
            for f in sorted(p["findings"]):
                counts[stage][0] += 1
                hit = [i for i, (s, pr, rx, _) in enumerate(expected)
                       if s == stage and pr == prog and rx.fullmatch(f)]
                if hit:
                    used.update(hit)
                else:
                    counts[stage][1] += 1
                    problems.append(f"new finding: {stage} {prog} {f}")
    for i, (s, pr, rx, required) in enumerate(expected):
        if required and i not in used:
            problems.append(f"expected but not found: {s} {pr} {rx.pattern}")

    print("")
    print("============================ RESULTS ============================")
    for s in STAGES:
        total, new = counts[s]
        req = sum(1 for e in expected if e[0] == s and e[3])
        may = sum(1 for e in expected if e[0] == s and not e[3])
        print(f"  {s:<9} {total:2d} findings  (expected: {req} required"
              f"{f' + {may} maybe' if may else ''}; new: {new})")
    if problems:
        print("")
        for p in problems:
            print(f"  - {p}")
    print("  Expected list: Tests/expected_findings.txt   Logs: Tests/results/")
    print("=================================================================")
    if problems:
        print(f"UNEXPECTED: {len(problems)} difference(s): " + "; ".join(problems))
        return 1
    print("All results as expected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
