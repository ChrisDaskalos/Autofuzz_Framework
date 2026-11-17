# File: autofuzz/__main__.py
"""
AutoFuzz command line.

  autofuzz init       write a starter autofuzz.yaml in this folder
  autofuzz check      check that clang, CMocka, libFuzzer and libclang are installed
  autofuzz generate   write the test sources into <output_dir>/gen
  autofuzz build      generate + compile
  autofuzz run        check + generate + compile + run edge tests and fuzzers
  autofuzz clean      remove what AutoFuzz created in <output_dir>

`autofuzz` is the same as `python3 -m autofuzz`.
"""
import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import config as config_mod
from . import runner

TEMPLATE = Path(__file__).resolve().parent / "init_template.yaml"


def _load(args, require_sources: bool = True) -> config_mod.Config:
    try:
        return config_mod.load(args.config, require_sources=require_sources)
    except config_mod.ConfigError as e:
        config_mod.die(e)
        raise  # not reached


def _out(args, cfg: config_mod.Config) -> Path:
    return Path(args.output_dir).resolve() if getattr(args, "output_dir", None) else cfg.output_dir


def _need_tools(cc: str, need_fuzz: bool = True) -> None:
    missing = runner.check_tools(cc, need_fuzz)
    if missing:
        runner.report_missing(missing)
        sys.exit(2)


def cmd_init(args) -> int:
    dest = Path(args.config) if args.config else Path.cwd() / config_mod.DEFAULT_CONFIG_NAME
    if dest.exists():
        print(f"autofuzz: {dest} already exists. It was not changed.", file=sys.stderr)
        return 1
    dest.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"autofuzz: wrote {dest}")
    print("Next: list your .c files under 'sources:', then run:  autofuzz run")
    return 0


def cmd_check(args) -> int:
    cc = "clang"
    if args.config or (Path.cwd() / config_mod.DEFAULT_CONFIG_NAME).exists():
        cc = _load(args, require_sources=False).compiler
    missing = runner.check_tools(cc)
    if missing:
        runner.report_missing(missing)
        return 2
    import subprocess
    ver = subprocess.run([cc, "--version"], stdout=subprocess.PIPE, universal_newlines=True).stdout.splitlines()[0]
    print(f">>> All dependencies found ({ver}; Python {sys.version.split()[0]})")
    return 0


def cmd_generate(args) -> int:
    cfg = _load(args)
    missing = runner.check_tools(cfg.compiler, need_compiler=False)  # generate needs only libclang
    if missing:
        runner.report_missing(missing)
        return 2
    out = _out(args, cfg)
    names = runner.generate(cfg, out)
    print(f"autofuzz: {2 * len(names)} files in {out / 'gen'}")
    return 0 if names else 1


def _generate_and_build(args, cfg, out):
    _need_tools(cfg.compiler)
    names = runner.generate(cfg, out)
    if not names:
        sys.exit(1)
    try:
        return runner.build(cfg, out, names)
    except runner.BuildError as e:
        config_mod.die(e)


def cmd_build(args) -> int:
    cfg = _load(args)
    built = _generate_and_build(args, cfg, _out(args, cfg))
    print(f">>> Build complete: {len(built['edge'])} edge tests, {len(built['fuzz'])} fuzzers"
          + (f", {len(built['skipped'])} skipped" if built["skipped"] else ""))
    return 0


def cmd_run(args) -> int:
    cfg = _load(args)
    out = _out(args, cfg)
    if args.fresh:
        runner.reset_fuzz_state(out)
    built = _generate_and_build(args, cfg, out)
    L = runner.Layout(out)
    seconds = args.fuzz_seconds if args.fuzz_seconds is not None else cfg.fuzz_seconds
    found = 0
    if args.only in (None, "edge"):
        print(">>> Running edge tests...")
        found += runner.run_edge(L, built["edge"])
    if args.only in (None, "fuzz"):
        print(f">>> Running fuzzers ({seconds} s each)...")
        found += runner.run_fuzz(L, built["fuzz"], seconds)
    print("")
    print(f">>> {found} program(s) found something. Logs: {L.logs}  Crash inputs: {L.crashes}")
    for s in built["skipped"]:
        print(f"    SKIPPED: {s}")
    return 1 if found else 0


def cmd_clean(args) -> int:
    cfg = _load(args, require_sources=False)
    out = _out(args, cfg)
    removed = runner.clean(out)
    print(f"autofuzz: removed {len(removed)} folder(s) in {out}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="autofuzz", description="Generate and run edge tests and fuzzers for C functions.")
    sub = ap.add_subparsers(dest="cmd", metavar="COMMAND")

    def add(name: str, func, helptext: str):
        p = sub.add_parser(name, help=helptext, description=helptext)
        p.add_argument("--config", "-c", metavar="FILE", help="config file (default: ./autofuzz.yaml)")
        p.set_defaults(func=func)
        return p

    add("init", cmd_init, "write a starter autofuzz.yaml (never overwrites)")
    add("check", cmd_check, "check that the needed tools are installed")
    for name, func, h in (("generate", cmd_generate, "write the test sources"),
                          ("build", cmd_build, "generate and compile"),
                          ("clean", cmd_clean, "remove the files AutoFuzz created")):
        add(name, func, h).add_argument("--output-dir", metavar="DIR", help="instead of output_dir from the config")
    p = add("run", cmd_run, "check tools, generate, compile, run")
    p.add_argument("--output-dir", metavar="DIR", help="instead of output_dir from the config")
    p.add_argument("--only", choices=["edge", "fuzz"], help="run only the edge tests or only the fuzzers")
    p.add_argument("--fuzz-seconds", type=int, metavar="N", help="seconds per fuzzer (instead of fuzz.seconds)")
    p.add_argument("--fresh", action="store_true", help="forget the old corpus, crashes and logs first")

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
