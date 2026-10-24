"""Isolated InternVL/Qwen2 QKV-to-BPU experiment; never edits the live service.

Requires gguf, numpy and onnx. Output contains model weights: keep it private.
The Conv is exactly a linear projection over each token, not an image model.
"""
import argparse
import json
from pathlib import Path
import numpy as np


def projection_model(weight, bias, tokens):
    import onnx
    from onnx import helper, numpy_helper, TensorProto
    weight=np.asarray(weight,dtype=np.float32);bias=np.asarray(bias,dtype=np.float32)
    if weight.ndim!=2 or bias.shape!=(weight.shape[0],) or tokens<1:
        raise ValueError('Invalid QKV dimensions')
    node=helper.make_node('Conv',['hidden','weight','bias'],['qkv'],kernel_shape=[1,1])
    graph=helper.make_graph([node],'language_qkv',
        [helper.make_tensor_value_info('hidden',TensorProto.FLOAT,[1,weight.shape[1],1,tokens])],
        [helper.make_tensor_value_info('qkv',TensorProto.FLOAT,[1,weight.shape[0],1,tokens])],
        [numpy_helper.from_array(weight[:,:,None,None],'weight'),numpy_helper.from_array(bias,'bias')])
    model=helper.make_model(graph,opset_imports=[helper.make_opsetid('',13)])
    model.ir_version=8;onnx.checker.check_model(model)
    return model


def main():
    import gguf
    import onnx
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gguf',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--layer',type=int,default=0)
    parser.add_argument('--tokens',type=int,default=256)
    args=parser.parse_args()
    reader=gguf.GGUFReader(str(args.gguf));tensors={t.name:t for t in reader.tensors}
    def read(name):
        t=tensors[name]
        return np.asarray(gguf.quants.dequantize(t.data,t.tensor_type),dtype=np.float32).copy()
    prefix=f'blk.{args.layer}.attn_'
    weight=np.concatenate([read(prefix+k+'.weight') for k in ['q','k','v']],axis=0)
    bias=np.concatenate([read(prefix+k+'.bias').reshape(-1) for k in ['q','k','v']])
    output=args.output;output.mkdir(parents=True,exist_ok=True)
    ignore=output/'.gitignore'
    if not ignore.exists():ignore.write_text('*\n')
    name=f'layer{args.layer}_qkv_t{args.tokens}'
    onnx.save(projection_model(weight,bias,args.tokens),str(output/(name+'.onnx')))
    np.savez(output/'projection-private.npz',weight=weight,bias=bias,
             attn_norm=read(f'blk.{args.layer}.attn_norm.weight'))
    calibration=output/'calibration';calibration.mkdir(exist_ok=True)
    rng=np.random.default_rng(310024)
    for index in range(8):
        value=rng.standard_normal((1,weight.shape[1],1,args.tokens),dtype=np.float32)
        value*=float([.5,1,2,3][index%4])
        np.save(calibration/f'{index:02d}.npy',value)
    (output/'projection-meta.json').write_text(json.dumps({
        'layer':args.layer,'tokens':args.tokens,'input_channels':int(weight.shape[1]),
        'output_channels':int(weight.shape[0]),'scope':'QKV projection only; no attention or language generation',
        'calibration':'synthetic; not representative language accuracy validation'},indent=2))
    print(json.dumps({'model':name,'weight_shape':list(weight.shape),'tokens':args.tokens}))


if __name__=='__main__':main()
