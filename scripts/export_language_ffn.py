"""Export private InternVL Qwen2 SwiGLU FFN weights for an isolated BPU prototype."""
import argparse,json
from pathlib import Path
import numpy as np

def ffn_model(up,gate,down,tokens):
 import onnx
 from onnx import helper,numpy_helper,TensorProto
 up=np.asarray(up,np.float32);gate=np.asarray(gate,np.float32);down=np.asarray(down,np.float32)
 if up.ndim!=2 or gate.shape!=up.shape or down.shape!=(up.shape[1],up.shape[0]) or not 1<=tokens<=512:
  raise ValueError('Invalid SwiGLU dimensions or token bucket')
 nodes=[helper.make_node('Conv',['hidden','up'],['u'],kernel_shape=[1,1]),helper.make_node('Conv',['hidden','gate'],['g'],kernel_shape=[1,1]),helper.make_node('Sigmoid',['g'],['s']),helper.make_node('Mul',['g','s'],['silu']),helper.make_node('Mul',['silu','u'],['product']),helper.make_node('Conv',['product','down'],['output'],kernel_shape=[1,1])]
 initial=[numpy_helper.from_array(np.asarray(w,np.float32)[:,:,None,None],name) for name,w in [('up',up),('gate',gate),('down',down)]]
 graph=helper.make_graph(nodes,'language_ffn',[helper.make_tensor_value_info('hidden',TensorProto.FLOAT,[1,up.shape[1],1,tokens])],[helper.make_tensor_value_info('output',TensorProto.FLOAT,[1,down.shape[0],1,tokens])],initial)
 model=helper.make_model(graph,opset_imports=[helper.make_opsetid('',13)]);model.ir_version=8;onnx.checker.check_model(model);return model

def main():
 import gguf,onnx
 p=argparse.ArgumentParser();p.add_argument('--gguf',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--layer',type=int,default=0);p.add_argument('--tokens',type=int,default=256);a=p.parse_args()
 r=gguf.GGUFReader(str(a.gguf));ts={t.name:t for t in r.tensors};weights={}
 for name in ['up','gate','down']:
  t=ts[f'blk.{a.layer}.ffn_{name}.weight'];weights[name]=np.asarray(gguf.quants.dequantize(t.data,t.tensor_type),np.float32).copy()
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'.gitignore').write_text('*\n')
 onnx.save(ffn_model(**weights,tokens=a.tokens),str(a.output/f'ffn{a.layer}_t{a.tokens}.onnx'))
 print(json.dumps({'layer':a.layer,'tokens':a.tokens,'shapes':{k:list(v.shape) for k,v in weights.items()}}),flush=True)
if __name__=='__main__':main()
