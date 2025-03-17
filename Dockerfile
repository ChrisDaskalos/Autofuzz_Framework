FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    gcc \
    make \
    libcmocka-dev \
    gdb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

# 1) Debug: List /app
RUN echo "== Listing /app ==" && ls -la /app

# 2) Debug: List /app/Tests
RUN echo "== Listing /app/Tests ==" && ls -la /app/Tests

# 3) Switch to Tests/unit_tests
WORKDIR /app/Tests/unit_tests
RUN echo "== Listing /app/Tests/unit_tests ==" && ls -la

RUN if [ -f Makefile ]; then \
      echo "Found Makefile"; \
      make; \
    elif [ -f makefile ]; then \
      echo "Found makefile"; \
      make -f makefile; \
    elif [ -f GNUmakefile ]; then \
      echo "Found GNUmakefile"; \
      make -f GNUmakefile; \
    else \
      echo "No Makefile found"; \
      exit 1; \
    fi

CMD ["./run_tests.sh"]
