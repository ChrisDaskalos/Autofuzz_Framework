#!/usr/bin/env python3
"""
Compare the findings of `make test` with Tests/expected_findings.txt.

Reads:
  Tests/results/unit.log                       (hand-written tests, Tests/legacy_thesis)
  Tests/results/<prefix>edge.log, fuzz.log     (`autofuzz run` of each suite in SUITES,
                                                copied by Tests/run_suite.sh)
  Tests/results/<prefix>skipped.txt            (functions AutoFuzz skipped, per suite)
  Tests/fuzz_manual/out/<fuzzer>.log           (output of Tests/fuzz_manual)

Expected findings: Tests/expected_findings.txt plus the expected_findings.txt
of each example project in EXAMPLES (same format).

Prints one line per stage, then as the very last line either
  "All results as expected"            (exit code 0)
or
  "UNEXPECTED: ..."                     (exit code 1)
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from autofuzz.findings import parse, parse_expected, compare  # noqa: E402  (shared with the report)

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
RESULTS = TESTS / "results"
UNIT_DIR = TESTS / "legacy_thesis"
MANUAL_DIR = TESTS / "fuzz_manual"
MANUAL_FUZZERS = ["fuzz_protocol_session", "fuzz_protocol_cmd", "fuzz_uart_dma"]

# AutoFuzz suites: name -> (log prefix in Tests/results/, folder of its autofuzz.yaml).
# Stages: <prefix>edge and <prefix>fuzz; the "skipped" stage uses the suite name as program.
SUITES = {
    "legacy": ("", UNIT_DIR),
    "self": ("self-", TESTS / "autofuzz_selftest"),
    "real": ("real-", ROOT),                # autofuzz.yaml in the repo root: Core/Src
    "example": ("ex-", ROOT / "examples" / "ringbuf_cli"),
}
# Example projects that keep their own expected_findings.txt
EXAMPLES = [ROOT / "examples" / "ringbuf_cli"]
EXPECTED_FILES = [TESTS / "expected_findings.txt"] + [d / "expected_findings.txt" for d in EXAMPLES]
STAGES = ["unit"]
for _prefix, _ in SUITES.values():
    STAGES += [f"{_prefix}edge", f"{_prefix}fuzz"]
STAGES += ["skipped", "manual"]

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
            out[name] = {"findings": {f"SKIPPED {ln.strip()}" for ln in lines}, "done": True, "review": set()}
    return out


def load_expected():
    expected = []
    for path in EXPECTED_FILES:
        if not path.exists():
            sys.exit(f"missing: {path.relative_to(ROOT)}")
        for n, line in enumerate(read(path), 1):
            try:
                e = parse_expected(line, STAGES, f"{path.relative_to(ROOT)}:{n}")
            except ValueError as err:
                sys.exit(str(err))
            if e is not None:
                expected.append(e)
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
    found = {s: {prog: p["findings"] for prog, p in actual[s].items()} for s in STAGES}
    new, missing, _ = compare(found, expected)
    counts = {s: [sum(len(f) for f in found[s].values()), 0] for s in STAGES}  # [findings, unexpected]
    for stage, prog, f in new:
        counts[stage][1] += 1
        problems.append(f"new finding: {stage} {prog} {f}")
    for e in missing:
        problems.append(f"expected but not found: {e.stage} {e.program} {e.pattern}")

    print("")
    print("============================ RESULTS ============================")
    for s in STAGES:
        total, new = counts[s]
        req = sum(1 for e in expected if e.stage == s and e.required)
        may = sum(1 for e in expected if e.stage == s and not e.required)
        rev = sum(1 for p in actual[s].values() for f in p["findings"] if f.startswith("REVIEW"))
        print(f"  {s:<9} {total:2d} findings  (expected: {req} required"
              f"{f' + {may} maybe' if may else ''}; new: {new})"
              f"{f'  [{rev} need review, not firmware bugs]' if rev else ''}")
    if problems:
        print("")
        for p in problems:
            print(f"  - {p}")
    print("  Expected lists: " + ", ".join(str(p.relative_to(ROOT)) for p in EXPECTED_FILES))
    print("  Logs: Tests/results/")
    print("=================================================================")
    if problems:
        print(f"UNEXPECTED: {len(problems)} difference(s): " + "; ".join(problems))
        return 1
    print("All results as expected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
