"""Run PRIVATE single-projection artifacts on S100; no camera/service changes.

Stop competing BPU workloads externally for an isolated benchmark. CPU reference
is float32 NumPy BLAS, NOT llama.cpp's quantized language decoder. End-to-end
language speed or quality cannot be inferred from this microbenchmark.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time


def error_metrics(prediction,reference):
    import numpy as np
    prediction=np.asarray(prediction,dtype=np.float64).reshape(-1)
    reference=np.asarray(reference,dtype=np.float64).reshape(-1)
    if prediction.shape!=reference.shape or not np.isfinite(prediction).all() or not np.isfinite(reference).all():
        raise ValueError('Invalid projection comparison')
    pnorm=np.linalg.norm(prediction);rnorm=np.linalg.norm(reference)
    if min(pnorm,rnorm)<=0:raise ValueError('Zero projection cannot validate cosine')
    cosine=float(np.clip(np.dot(prediction,reference)/(pnorm*rnorm),-1,1))
    relative=float(np.linalg.norm(prediction-reference)/rnorm)
    return cosine,relative


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--tokens',type=int,default=256)
    parser.add_argument('--layer',type=int,default=0)
    parser.add_argument('--threads',type=int,default=6)
    parser.add_argument('--model',type=Path,help='Optional separately calibrated HBM')
    parser.add_argument('--inputs',type=Path,help='PRIVATE directory of saved post-RMSNorm NCHW activations')
    args=parser.parse_args()
    os.environ['OPENBLAS_NUM_THREADS']=str(args.threads)
    os.environ['OMP_NUM_THREADS']=str(args.threads)
    import numpy as np
    sys.path[:0]=[str(args.root),str(args.root/'vendor')]
    from hbm_runner import HbmRunner
    private=np.load(args.artifacts/'projection-private.npz')
    weight=private['weight'];bias=private['bias']
    before=time.perf_counter()
    run=HbmRunner(args.model or args.artifacts/f'layer{args.layer}_qkv_t{args.tokens}.hbm')
    load_ms=(time.perf_counter()-before)*1000
    rng=np.random.default_rng(750031)
    results=[];distinct=[]
    if args.inputs:
        paths=sorted(args.inputs.glob('*.npy'))
        if not paths:raise ValueError('No saved activations')
        cases=[(None,np.load(path)) for path in paths]
    else:
        cases=[(scale,rng.normal(size=(1,weight.shape[1],1,args.tokens)).astype('float32')*scale)
               for scale in [.25,.5,1,2,3,6]]
    for index,(scale,value) in enumerate(cases):
        value=np.ascontiguousarray(value,dtype=np.float32)
        if value.shape!=(1,weight.shape[1],1,args.tokens) or not np.isfinite(value).all():
            raise ValueError('Saved activation shape or values are invalid')
        hidden=value[0,:,0,:].T.copy()
        reference=hidden@weight.T+bias
        prediction=run(value)[0][0,:,0,:].T
        assert prediction.shape==reference.shape and np.isfinite(prediction).all()
        distinct.append(float(prediction[0,0]))
        cpu=[];bpu=[]
        # Separate phases: idle BLAS helper threads otherwise distort BPU timings.
        time.sleep(.25)
        for _ in range(3):run(value)
        for _ in range(20):
            start=time.perf_counter();run(value);bpu.append((time.perf_counter()-start)*1000)
        for _ in range(3):hidden@weight.T+bias
        for _ in range(20):
            start=time.perf_counter();hidden@weight.T+bias;cpu.append((time.perf_counter()-start)*1000)
        cosine,relative=error_metrics(prediction,reference)
        results.append({'case':index,'scale':scale,'cosine':cosine,'relative_l2':relative,
            'bpu_ms_median':float(np.median(bpu)),'cpu_float_blas_ms_median':float(np.median(cpu))})
    assert len(set(distinct))==len(distinct),'Outputs did not vary across inputs'
    summary={'layer':args.layer,'tokens':args.tokens,'threads':args.threads,'load_ms':load_ms,
        'scope':'Single QKV only; '+('saved real activations' if args.inputs else 'synthetic inputs')+'; CPU reference is float32 BLAS',
        'in_range_numeric_pass':all(x['cosine']>.999 and x['relative_l2']<.03 for x in results
                                    if x['scale'] is None or x['scale']<=3),
        'results':results}
    (args.artifacts/f'benchmark-t{args.tokens}.json').write_text(json.dumps(summary,indent=2))
    print('QKV_RESULT '+json.dumps(summary),flush=True)


if __name__=='__main__':main()
