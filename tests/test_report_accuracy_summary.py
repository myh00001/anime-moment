import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from summarize_report_accuracy import summarize


class AccuracySummaryTests(unittest.TestCase):
    def test_abstention_and_runtime_error_remain_in_denominator(self):
        rows=[dict(kind='public_original',group='shirt',accepted=['shirt'],status=s)
              for s in ['correct','wrong_specific','abstain','runtime_error']]
        out=summarize({'results':rows})['supported_public_originals']
        self.assertEqual(out['strict_accuracy_including_abstentions'],.25)
        self.assertEqual(out['precision_when_specific'],.5)
        self.assertEqual(out['specific_coverage'],.5)

    def test_unsupported_and_derived_neutral_do_not_inflate_accuracy(self):
        rows=[dict(kind='public_original',group='shirt',accepted=['shirt'],status='wrong_specific'),
              dict(kind='public_original',group='dress',accepted=[],status='abstain_unsupported'),
              dict(kind='derived',group='empty',accepted=[],status='correct_neutral')]
        out=summarize({'results':rows})
        self.assertEqual(out['supported_public_originals']['n'],1)
        self.assertEqual(out['supported_public_originals']['strict_accuracy_including_abstentions'],0)
