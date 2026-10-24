"""Build an experimental Qwen2 FFN hook using an EXISTING static b11669 build.

Only an isolated Unity object/archive/server is written. Production sources and
libraries are not overwritten. Requires the existing embedding bridge and the
matching model-specific HBM weights; this does not install or enable them.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess

START='        cur = build_ffn(cur,\n'
END='                LLM_FFN_SILU, LLM_FFN_PAR, il);'


def patch_qwen_source(text):
    if 's100_ffn_try' in text:
        if '#include "s100_ffn_bridge.h"' not in text:raise ValueError('Incomplete FFN patch')
        return text
    if text.count(START)!=1 or text.count(END)!=1 or text.count('#include "models.h"')!=1:
        raise ValueError('Unsupported Qwen2 graph; expected b11669')
    text=text.replace('#include "models.h"','#include "models.h"\n#include "s100_ffn_bridge.h"')
    text=text.replace(START,'        cur = s100_ffn_prepare(ctx0,cur,il);\n'
        '        if (auto * accelerated = s100_ffn_try(ctx0,cur,il)) {\n'
        '            cur = accelerated;\n        } else {\n'+START)
    return text.replace(END,END+'\n        }')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    root=args.root.resolve();local=root/'local-vlm';source=local/'llama.cpp-b11669';build=local/'build'
    flags={}
    for line in (build/'src/CMakeFiles/llama.dir/flags.make').read_text().splitlines():
        if line.startswith('CXX_'):
            key,value=line.split('=',1);flags[key.strip()]=shlex.split(value)
    previous_root=next(x[2:].split('/local-vlm/')[0] for x in flags['CXX_INCLUDES'] if x.startswith('-I') and '/local-vlm/' in x)
    rebase=lambda text:text.replace(previous_root,str(root))
    graph=source/'src/models/qwen2.cpp'
    units=[]
    for path in (build/'src/CMakeFiles/llama.dir/Unity').glob('*.cxx'):
        if str(graph) in rebase(path.read_text()):units.append(path)
    if len(units)!=1:raise RuntimeError('Expected exactly one static Unity compilation unit for Qwen2')
    output=local/'ffn-bridge-runtime';private=output/'source';private.mkdir(parents=True,exist_ok=True)
    (output/'bin').mkdir(exist_ok=True)
    copied=private/'qwen2.cpp';copied.write_text(patch_qwen_source(graph.read_text()))
    header=Path(__file__).resolve().parent/'experimental/s100_ffn_bridge.h'
    shutil.copy2(header,private/header.name)
    unit=private/units[0].name;unit.write_text(rebase(units[0].read_text()).replace(str(graph),str(copied)))
    obj=output/(unit.name+'.o')
    command=['/usr/bin/c++',*[rebase(x) for key in ['CXX_DEFINES','CXX_INCLUDES','CXX_FLAGS'] for x in flags[key]],
        '-I'+str(source/'src/models'),'-c',str(unit),'-o',str(obj)]
    with (output/'build.log').open('w') as log:subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
    archive=output/'libllama.a';shutil.copy2(build/'src/libllama.a',archive)
    subprocess.run(['ar','r',str(archive),str(obj)],check=True)
    subprocess.run(['ranlib',str(archive)],check=True)
    command=shlex.split((build/'tools/server/CMakeFiles/llama-server.dir/link.txt').read_text())
    binary=output/'bin/llama-server';command[command.index('-o')+1]=str(binary)
    command=[str(archive) if token=='../../src/libllama.a' else token for token in command]
    subprocess.run(command,cwd=build/'tools/server',check=True)
    data=binary.read_bytes()
    if b'S100_FFN_USED' not in data or b'S100 embedding accepted' not in data:
        raise RuntimeError('Experimental FFN or visual embedding bridge is missing')
    subprocess.run([str(binary),'--version'],check=True)
    (output/'build-description.json').write_text(json.dumps({'source':'b11669','binary_sha256':hashlib.sha256(data).hexdigest(),
        'header_sha256':hashlib.sha256(header.read_bytes()).hexdigest(),'production_enabled':False},indent=2))
    print('Built isolated experimental server:',binary)


if __name__=='__main__':main()
