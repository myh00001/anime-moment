"""Prepare separately distributed report assets; requires numpy, tokenizers, ORT.

Run on a development machine with a roomy --output directory (e.g. D:).
No model, photograph or generated PDF belongs in the source repository.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

BASE = 'https://huggingface.co/Marqo/marqo-fashionSigLIP/resolve/main/'
ASSETS = {
    'vision.onnx': (BASE+'onnx/vision_model_quantized.onnx',
                    'f1009cfce0eedd409f601e8351eedab72e8529641105eee6517821a9a634a2f4'),
    'text.onnx': (BASE+'onnx/text_model_quantized.onnx',
                  'f5a7995e029c6ee9346fa46857661c4a171d28b164fa7703b85a527d73adf170'),
    'tokenizer.json': (BASE+'tokenizer.json',
                       '5bc9b16db0e7adf5c9a2bd57f8f9c8e6ebdaabe75679cc956d007f78036d5b4a'),
    'person.onnx': ('https://media.githubusercontent.com/media/opencv/opencv_zoo/main/'
                    'models/object_detection_yolox/object_detection_yolox_2022nov.onnx',
                    'c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063'),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(output, activate=False):
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer
    output.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in ASSETS.items():
        path = output/name
        if not path.exists():
            temporary = path.with_suffix('.partial')
            with urllib.request.urlopen(url, timeout=90) as response, temporary.open('wb') as stream:
                shutil.copyfileobj(response, stream)
            if digest(temporary) != expected:
                raise ValueError('Downloaded asset checksum mismatch: '+name)
            temporary.replace(path)
        if digest(path) != expected:
            raise ValueError('Existing asset checksum mismatch: '+name)
    prompts = json.loads(Path(__file__).with_name('report-category-prompts.json').read_text())
    tokenizer = Tokenizer.from_file(str(output/'tokenizer.json'))
    tokenizer.enable_padding(length=64, pad_id=1, pad_token='</s>')
    tokenizer.enable_truncation(max_length=64)
    session = ort.InferenceSession(str(output/'text.onnx'), providers=['CPUExecutionProvider'])
    features = []
    for label, words in prompts['labels'].items():
        texts = [template.format(word) for template in prompts['templates'] for word in words]
        ids = np.array([item.ids for item in tokenizer.encode_batch(texts)], dtype=np.int64)
        vectors = session.run(None, {'input_ids': ids})[0]
        vectors /= np.linalg.norm(vectors, axis=-1, keepdims=True)
        vector = vectors.mean(0)
        features.append(vector/np.linalg.norm(vector))
    np.savez(output/'categories.npz', labels=np.array(list(prompts['labels'])),
             features=np.array(features, dtype=np.float32))
    manifest = {'schema': 1, 'validated': activate,
                'vision_source': BASE, 'person_source': ASSETS['person.onnx'][0],
                'sha256': {name: digest(output/name) for name in
                           ('person.onnx', 'vision.onnx', 'categories.npz')},
                'note': 'Validate on deployment data before activating; similarity is not probability.'}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('Prepared', output, 'activated:', activate)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--activate', action='store_true', help='Enable only after local validation')
    args = parser.parse_args()
    prepare(args.output, args.activate)
