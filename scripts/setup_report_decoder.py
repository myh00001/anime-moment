#!/usr/bin/env python3
"""Build an isolated deterministic S100 VLM node; never install system libraries."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

COMMIT = '439f23f6c9b09eaebcf84027a0911c220fb4fb34'


def source_tree(url, destination):
    if destination.is_dir():
        return
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(100_000_001)
    if len(data) > 100_000_000:
        raise ValueError('Unexpected source archive size')
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        stage = Path(temporary) / 'source'
        stage.mkdir()
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            for member in archive.getmembers():
                if not (member.isfile() or member.isdir()):
                    continue
                parts = Path(member.name).parts[1:]
                if not parts:
                    continue
                target = stage.joinpath(*parts).resolve()
                if not target.is_relative_to(stage.resolve()):
                    raise ValueError('Unsafe source archive path')
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.extractfile(member).read())
        stage.rename(destination)


def prepare(root):
    folder = root / 'local-vlm/greedy-vlm-build'
    folder.mkdir(parents=True, exist_ok=True)
    source_tree('https://api.github.com/repos/D-Robotics/hobot_llamacpp/tarball/' + COMMIT,
                folder / 'hobot_llamacpp')
    source_tree('https://api.github.com/repos/ggml-org/llama.cpp/tarball/b4749',
                folder / 'llama.cpp')
    source = folder / 'hobot_llamacpp'
    link = source / 'llama.cpp'
    if not link.exists():
        link.symlink_to(folder / 'llama.cpp', target_is_directory=True)
    parser = source / 'src/s100/llama_cpp_parser.cpp'
    text = parser.read_text()
    text = text.replace('params.sampling.temp = 0.5;',
                        'params.sampling.temp = 0.0;\n  params.sampling.seed = 0;')
    if 'params.sampling.temp = 0.0;' not in text or 'params.sampling.seed = 0;' not in text:
        raise ValueError('Unexpected official sampler source')
    parser.write_text(text)
    cmake = source / 'CMakeLists.txt'
    cmake.write_text(cmake.read_text().replace(
        '${CMAKE_CURRENT_SOURCE_DIR}/llama.cpp/build/common/libcommon.a', 'common'))
    command = ('source /opt/tros/humble/setup.bash && '
               'cmake -S "$1" -B "$2" -DPLATFORM_S100=ON -DSHARED_MEM=OFF '
               '-DLLAMA_BUILD_COMMON=ON -DLLAMA_BUILD_TESTS=OFF '
               '-DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=OFF '
               '-DLLAMA_CURL=OFF -DGGML_NATIVE=OFF -DGGML_CCACHE=OFF && '
               'nice -n 15 cmake --build "$2" --target hobot_llamacpp -j2')
    with (folder / 'setup-build.log').open('w') as log:
        subprocess.run(['bash', '-c', command, 'report-decoder', str(source), str(folder / 'build')],
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=1200)
    binary = folder / 'build/hobot_llamacpp'
    check = ('source /opt/tros/humble/setup.bash && '
             'export LD_LIBRARY_PATH=/opt/tros/humble/lib/aarch64-linux-gnu:$LD_LIBRARY_PATH && '
             'ldd -r "$1"')
    result = subprocess.run(['bash', '-c', check, 'report-decoder', str(binary)],
                            capture_output=True, text=True, check=True)
    if 'not found' in result.stdout or 'undefined symbol' in result.stdout:
        raise RuntimeError('Decoder is incompatible with installed libraries')
    target = root / 'local-vlm/report-runtime'
    target.mkdir(exist_ok=True)
    temporary = target / 'hobot_llamacpp.tmp'
    shutil.copy2(binary, temporary)
    temporary.chmod(0o755)
    digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
    temporary.replace(target / 'hobot_llamacpp')
    manifest = {'source_commit': COMMIT, 'llama_tag': 'b4749', 'temperature': 0,
                'seed': 0, 'threads': 6, 'sha256': digest}
    temporary = target / 'manifest.tmp'
    temporary.write_text(json.dumps(manifest, indent=2))
    temporary.replace(target / 'manifest.json')
    print('Prepared isolated report decoder:', target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/home/sunrise/anime-camera'))
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() != 'aarch64':
        parser.error('Run this optional builder on the S100')
    prepare(args.root.resolve())
