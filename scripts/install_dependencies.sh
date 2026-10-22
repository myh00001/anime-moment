#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
sudo apt-get update
sudo apt-get install -y python3-pip python3-gi python3-gi-cairo python3-cairo gir1.2-gtk-3.0 gir1.2-pango-1.0 v4l-utils
if [ -d "$root/service/wheelhouse" ]; then
    python3 -m pip install --no-index --find-links "$root/service/wheelhouse" --target "$root/service/vendor" -r "$root/service/requirements.txt"
else
    python3 -m pip install --target "$root/service/vendor" -r "$root/service/requirements.txt"
fi
printf '%s\n' 'Dependencies installed. HBRT/hbm_runtime must be supplied by the board system.'
