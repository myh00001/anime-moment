import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'service'))
from report_bpu_caption import decoder_profile, NODE


class ReportDecoderTests(unittest.TestCase):
    def test_missing_or_invalid_manifest_keeps_official_decoder(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.assertEqual(decoder_profile(root)['node'],NODE)
            runtime=root/'local-vlm/report-runtime';runtime.mkdir(parents=True)
            for value in ['bad json','[]','{}']:
                (runtime/'manifest.json').write_text(value)
                self.assertEqual(decoder_profile(root)['node'],NODE)

    def test_verified_decoder_selected_and_tampered_binary_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime=Path(folder)/'local-vlm/report-runtime';runtime.mkdir(parents=True)
            binary=runtime/'hobot_llamacpp';binary.write_bytes(b'validated fixture');binary.chmod(0o755)
            manifest={'source_commit':'439f23f6c9b09eaebcf84027a0911c220fb4fb34',
                      'temperature':0,'seed':0,'threads':6,
                      'sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}
            (runtime/'manifest.json').write_text(json.dumps(manifest))
            selected=decoder_profile(folder)
            self.assertEqual(selected['node'],str(binary));self.assertEqual(selected['threads'],6)
            binary.write_bytes(b'changed fixture')
            self.assertEqual(decoder_profile(folder)['node'],NODE)


if __name__=='__main__':unittest.main()
