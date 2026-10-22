#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
# Never overwrite a mapped library: link to a temporary name, then rename.
temporary="$(mktemp "$root/service/_image_kernels.XXXXXX.so")"
trap 'rm -f "$temporary"' EXIT
cc -O3 -std=c11 -fPIC -shared -fopenmp -DNATIVE_THREADS=2 \
  -ffp-contract=off -fno-fast-math "$root/service/image_kernels.c" -o "$temporary"
mv "$temporary" "$root/service/_image_kernels.so"
