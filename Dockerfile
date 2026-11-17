# AutoFuzz test environment: Ubuntu 24.04 + clang 18 + libFuzzer + CMocka.
#
#   docker build -t autofuzz .
#   docker run --rm autofuzz                                   # = make test
#   docker run --rm autofuzz make fuzz FUZZ_MAX_SECS=300       # longer fuzzing
#
# This image is only for the PC tests. It does not build the STM32 firmware.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# clang-18           compiler
# libclang-rt-18-dev libFuzzer + AddressSanitizer/UBSan runtimes
# llvm-18            llvm-symbolizer, so sanitizer reports show file:line
# build-essential    C library headers, make
# libcmocka-dev      unit test framework
# python3-venv       for AutoFuzz (libclang + PyYAML from requirements.txt)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        clang-18 libclang-rt-18-dev llvm-18 \
        build-essential make libcmocka-dev \
        python3 python3-venv ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && ln -s /usr/bin/clang-18 /usr/local/bin/clang

ENV ASAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-18

# Python packages in a virtual environment (Ubuntu 24.04 blocks
# system-wide pip installs). Copied first so Docker can cache this step.
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /app
COPY . /app

# Check the tools and compile everything while building the image.
RUN make build

CMD ["make", "test"]
