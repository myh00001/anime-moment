#!/usr/bin/env python3
"""Install the current local report writer service without downloading models."""
from pathlib import Path
import subprocess


def main():
    root = Path(__file__).resolve().parents[1] / 'service'
    for relative in ('run_report_models.py', 'local-vlm/build/bin/llama-server',
                     'local-vlm/Qwen3-0.6B-Q8_0.gguf'):
        if not (root / relative).is_file():
            raise SystemExit('Missing required runtime: ' + relative)
    # systemd quoted strings need literal percent escaping as well as quotes.
    def quote(path):
        return '"' + str(path).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'
    units = Path.home() / '.config/systemd/user'
    units.mkdir(parents=True, exist_ok=True)
    unit = f'''[Unit]
Description=Anime Moment local report writer

[Service]
WorkingDirectory={quote(root)}
ExecStart=/usr/bin/python3 {quote(root / 'run_report_models.py')}
Environment=OMP_NUM_THREADS=2
Environment=FESTIVAL_VLM_SINGLE_VIEW=1
Nice=10
CPUQuota=160%
MemoryMax=3G
Restart=no
TimeoutStopSec=10
'''
    (units / 'anime-report-vlm.service').write_text(unit, encoding='utf-8')
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    print('Installed on-demand local report writer service; existing camera startup is unchanged.')


if __name__ == '__main__':
    main()
