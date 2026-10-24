"""Supervise the current local Chinese report writer."""
from pathlib import Path
import signal
import subprocess
import threading

def main():
    root=Path(__file__).resolve().parent/'local-vlm';binary=root/'build/bin/llama-server'
    common=[str(binary),'--host','127.0.0.1','--ctx-size','2048','--threads','2',
            '--threads-batch','2','--parallel','1','--batch-size','128','--ubatch-size','128',
            '--n-gpu-layers','0','--jinja','--no-webui','--sleep-idle-seconds','300']
    commands=[common+['--model',str(root/'Qwen3-0.6B-Q8_0.gguf'),
        '--alias','local-report-writer','--port','8088']]
    stopping=threading.Event();children=[]
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:stopping.set())
    try:
        for command in commands:children.append(subprocess.Popen(command))
        while not stopping.wait(.5):
            if any(child.poll() is not None for child in children):raise RuntimeError('Local report model exited')
    finally:
        for child in children:
            if child.poll() is None:child.terminate()
        for child in children:
            try:child.wait(timeout=6)
            except subprocess.TimeoutExpired:child.kill();child.wait()

if __name__=='__main__':main()
