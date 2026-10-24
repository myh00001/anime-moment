"""Build the opt-in S100 embedding bridge against an existing b11669 source tree.

Run on the board, with cmake and a C++ compiler already installed. Model weights
are intentionally not downloaded or included by this script.
"""
import argparse
from pathlib import Path
import subprocess

NEEDLE='    out_embd.resize((size_t)n_embd_out * n_tokens_out);\n'
BRIDGE=r'''
    // Opt-in host-owned BPU embedding, serialized with the original photo.
    if (const char * path = std::getenv("S100_VLM_EMBED_FILE")) {
        FILE * file = std::fopen(path, "rb");
        if (!file) return 1;
        uint32_t header[3] = {};
        bool ok = std::fread(header, sizeof(uint32_t), 3, file) == 3
            && header[0] == 0x53313030 && header[1] == n_tokens_out
            && header[2] == (uint32_t)n_embd_out;
        if (ok) ok = std::fread(out_embd.data(), sizeof(float), out_embd.size(), file) == out_embd.size();
        if (ok) ok = std::fgetc(file) == EOF;
        std::fclose(file);
        if (ok) ok = std::all_of(out_embd.begin(), out_embd.end(), [](float x) { return std::isfinite(x); });
        if (!ok) { LOG_ERR("S100 embedding rejected: shape/data mismatch\n"); return 1; }
        LOG_INF("S100 embedding accepted: %d tokens x %d features\n", (int)n_tokens_out, n_embd_out);
        return 0;
    }
'''


def patch_source(text):
    if 'S100_VLM_EMBED_FILE' in text:return text
    if text.count(NEEDLE)!=1:raise ValueError('Unsupported mtmd source; expected b11669 embedding allocation')
    return text.replace(NEEDLE,NEEDLE+BRIDGE)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True,help='Flat installed service directory on S100')
    parser.add_argument('--jobs',type=int,default=2)
    args=parser.parse_args()
    local=args.root.resolve()/'local-vlm'
    source=local/'llama.cpp-b11669'
    target=source/'tools/mtmd/mtmd.cpp'
    old=target.read_text();new=patch_source(old)
    if new!=old:
        backup=target.with_suffix('.before-general-report.cpp')
        if not backup.exists():backup.write_text(old)
        target.write_text(new)
    build=local/'build-general-report'
    subprocess.run(['cmake','-S',str(source),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release',
        '-DBUILD_SHARED_LIBS=OFF','-DGGML_BLAS=OFF','-DGGML_OPENMP=ON','-DLLAMA_CURL=OFF',
        '-DLLAMA_BUILD_TESTS=OFF','-DLLAMA_BUILD_EXAMPLES=OFF','-DLLAMA_BUILD_SERVER=ON'],check=True)
    subprocess.run(['cmake','--build',str(build),'--target','llama-server','-j',str(args.jobs)],check=True)
    binary=build/'bin/llama-server'
    if b'S100 embedding accepted' not in binary.read_bytes():raise RuntimeError('Embedding bridge missing from binary')
    subprocess.run([str(binary),'--version'],check=True)
    (build/'.bridge-ready').write_text('b11669 S100 original-image embedding bridge\n')
    print('Built and checked:',binary)


if __name__=='__main__':main()
