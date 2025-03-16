#!/usr/bin/env bash
#
# run_tests.sh
# ------------
# A small script to automatically find and run all *.elf files
# in the current directory. Good for quickly running your CMocka tests
# without manually typing each command.

# Exit immediately on any command failure:
set -e

echo "=== Running All Test ELF Binaries in $(pwd) ==="

# Loop over every ELF file
for elf in *.elf; do
  # Check if the file is truly executable
  if [ -x "$elf" ]; then
    echo "-----"
    echo "Running test: $elf"
    "./$elf"   # Execute the test
    echo
  fi
done

echo "=== All tests attempted. ==="
