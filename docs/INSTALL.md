# Install AutoFuzz

AutoFuzz runs on a Linux PC. It needs:

| What | Why |
|---|---|
| clang (10 or newer) | compiles the tests, with AddressSanitizer, UBSan and libFuzzer |
| the clang runtime libraries | the sanitizers and libFuzzer |
| CMocka | the edge tests are CMocka programs |
| Python 3.8 or newer | runs AutoFuzz |
| Python packages `libclang` and `PyYAML` | read your C code; read `autofuzz.yaml` |

`autofuzz check` (or `make deps` in this repository) tells you what is
missing and the exact command to install it. `autofuzz run` does the same
check first and stops if something is missing.

## Ubuntu 20.04 (the developer VM, Python 3.8, clang 10)

```bash
sudo apt update
sudo apt install clang-10 libclang-common-10-dev llvm-10 \
                 build-essential make libcmocka-dev python3 python3-venv
sudo ln -sf /usr/bin/clang-10 /usr/local/bin/clang   # only if `clang` is not found

cd ServoProject
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip           # the pip of Ubuntu 20.04 is too old for some wheels
pip install -r requirements.txt     # libclang + PyYAML

make deps                           # >>> All dependencies found (clang version 10...)
make test                           # last line: All results as expected
```

`Dockerfile.ubuntu20` does exactly these steps. GitHub Actions runs it in
the `ubuntu20` job.

## Ubuntu 24.04 (clang 18)

```bash
sudo apt update
sudo apt install clang-18 libclang-rt-18-dev llvm-18 \
                 build-essential make libcmocka-dev python3 python3-venv
sudo ln -sf /usr/bin/clang-18 /usr/local/bin/clang
export ASAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-18

python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
make deps && make test
```

On Ubuntu 23.04 and newer, the libFuzzer and sanitizer runtimes are in
`libclang-rt-<N>-dev`. On older releases, they are in `libclang-common-<N>-dev`.

## Docker (nothing to install except Docker)

```bash
docker build -t autofuzz . && docker run --rm autofuzz                     # Ubuntu 24.04
docker build -f Dockerfile.ubuntu20 -t autofuzz:ubuntu20 . \
  && docker run --rm autofuzz:ubuntu20                                     # Ubuntu 20.04
```

## The `autofuzz` command

In this repository you do not have to install anything else: the Makefile
runs the tool as `python3 -m autofuzz` from the repository root.

To use the short command `autofuzz` in any folder (for your own project),
install the package into the same virtual environment:

```bash
pip install .            # from the repository root
autofuzz --help
```

`autofuzz` and `python3 -m autofuzz` are the same program.

## If `autofuzz check` says something is missing

| Message | Install command |
|---|---|
| `clang (C compiler)` | `sudo apt install clang` |
| `CMocka (unit test library)` | `sudo apt install libcmocka-dev` |
| `libFuzzer for clang` or `AddressSanitizer/UBSan runtime` | clang 15+: `sudo apt install libclang-rt-<N>-dev`; older: `sudo apt install libclang-common-<N>-dev` (`<N>` = the clang major version) |
| `libFuzzer (gcc cannot build fuzzers, only clang can)` | `sudo apt install clang` and set `compiler: clang` in `autofuzz.yaml` |
| `libclang (Python package ...)` | `pip install libclang==18.1.1` |
| `PyYAML (Python package)` | `pip install PyYAML` |

The `libclang` pip package includes its own copy of the libclang library,
so it does not have to match the clang version you compile with. To use the
system library instead, set `CLANG_LIB=/path/to/libclang.so` or
`LIBCLANG_PATH=/usr/lib/llvm-10/lib`.
