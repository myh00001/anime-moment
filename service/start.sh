#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="$PWD/vendor${PYTHONPATH:+:$PYTHONPATH}"
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=4
exec python3 server.py
