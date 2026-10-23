#!/usr/bin/env python3
"""Prepare a small local VLM and install an on-demand user service on S100."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

TAG='b11669'
FILES={'Qwen3-0.6B-Q8_0.gguf':639446688,
       'SmolVLM2-256M-Video-Instruct-Q8_0.gguf':175056256,
       'mmproj-SmolVLM2-256M-Video-Instruct-Q8_0.gguf':103771616}

def download(url,target,size=None):
    if target.exists() and (size is None or target.stat().st_size==size):return
    partial=target.with_suffix(target.suffix+'.part')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url,timeout=60) as source,partial.open('wb') as output:
        shutil.copyfileobj(source,output)
    if size is not None and partial.stat().st_size!=size:
        raise RuntimeError('Incomplete download: '+target.name)
    partial.replace(target)

def patch_single_view(source):
    """Expose a global-view-only mode equivalent to disabling image splitting."""
    path=source/'tools/mtmd/mtmd-image.cpp';text=path.read_text()
    if 'FESTIVAL_VLM_SINGLE_VIEW' in text:return
    start=text.index('mtmd_image_preproc_out mtmd_image_preprocessor_idefics3::preprocess')
    # Restrict the custom-token-limit path to an overview when opted in.
    marker='''    output.append_overview(hparams, sliced.overview, true);
    output.append(hparams, sliced.slices, true);
    output.grid_x = instructions.grid_size.width;
    output.grid_y = instructions.grid_size.height;'''
    position=text.index(marker,start)
    replacement='''    output.append_overview(hparams, sliced.overview, true);
    if (std::getenv("FESTIVAL_VLM_SINGLE_VIEW") == nullptr) {
        output.append(hparams, sliced.slices, true);
        output.grid_x = instructions.grid_size.width;
        output.grid_y = instructions.grid_size.height;
    }'''
    text='#include <cstdlib>\n'+text[:position]+text[position:].replace(marker,replacement,1)
    path.write_text(text)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True,help='Directory containing festival.py')
    parser.add_argument('--prepare',action='store_true',help='Download ~1GB and build llama-server on this board')
    args=parser.parse_args();root=args.root.resolve();assets=root/'local-vlm';assets.mkdir(exist_ok=True)
    if args.prepare:
        if shutil.disk_usage(root).free<3*1024**3:raise RuntimeError('At least 3GB free disk space is required')
        for name,size in FILES.items():
            repo='ggml-org/SmolVLM2-256M-Video-Instruct-GGUF' if 'SmolVLM' in name else 'Qwen/Qwen3-0.6B-GGUF'
            download('https://hf-mirror.com/'+repo+'/resolve/main/'+name+'?download=true',assets/name,size)
        archive=assets/('llama-'+TAG+'-source.tar.gz')
        download('https://codeload.github.com/ggml-org/llama.cpp/tar.gz/refs/tags/'+TAG,archive)
        source=assets/('llama.cpp-'+TAG)
        if not source.exists():
            with tarfile.open(archive) as package:package.extractall(assets,filter='data')
        patch_single_view(source)
        subprocess.run(['cmake','-S',str(source),'-B',str(assets/'build'),'-DCMAKE_BUILD_TYPE=Release',
            '-DGGML_NATIVE=OFF','-DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod','-DLLAMA_BUILD_TESTS=OFF',
            '-DLLAMA_BUILD_EXAMPLES=OFF','-DLLAMA_BUILD_UI=OFF','-DLLAMA_USE_PREBUILT_UI=OFF',
            '-DLLAMA_CURL=OFF','-DBUILD_SHARED_LIBS=OFF'],check=True)
        subprocess.run(['nice','-n','15','cmake','--build',str(assets/'build'),'--target','llama-server','-j','2'],check=True)
    binary=assets/'build/bin/llama-server'
    if not binary.is_file():raise RuntimeError('llama-server not built; run with --prepare first')
    for name,size in FILES.items():
        if not (assets/name).is_file() or (assets/name).stat().st_size!=size:
            raise RuntimeError('Missing or incomplete model: '+name)
    # ExecStart values use systemd's quoting syntax; reject metacharacters in root.
    if any(char in str(root) for char in '\n\r"%'):raise ValueError('Unsupported installation path')
    wrapper=root/'run_report_models.py'
    if not wrapper.is_file():raise RuntimeError('Deploy service/run_report_models.py to the application directory first')
    command=f'/usr/bin/python3 "{wrapper}"'
    unit=Path.home()/'.config/systemd/user/anime-report-vlm.service';unit.parent.mkdir(parents=True,exist_ok=True)
    unit.write_text('[Unit]\nDescription=Local image-grounded festival newspaper reporter\n'
        '[Service]\nType=simple\nWorkingDirectory='+str(root)+'\nExecStart='+command+'\n'
        'Environment=OMP_NUM_THREADS=2\nEnvironment=FESTIVAL_VLM_SINGLE_VIEW=1\nNice=10\nCPUQuota=160%\nMemoryMax=3G\n'
        'Restart=no\nTimeoutStopSec=10\n',encoding='utf-8')
    env=dict(os.environ,XDG_RUNTIME_DIR=f'/run/user/{os.getuid()}',
        DBUS_SESSION_BUS_ADDRESS=f'unix:path=/run/user/{os.getuid()}/bus')
    subprocess.run(['systemctl','--user','daemon-reload'],env=env,check=True)
    print('Installed on-demand local VLM service; camera autostart was not changed.')

if __name__=='__main__':main()
