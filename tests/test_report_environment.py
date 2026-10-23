import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'service'))
import report_environment as module


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        module._overlay = None

    def tearDown(self):
        module._overlay = None

    def test_success_cached_but_current_environment_retained(self):
        raw = b'AMENT_PREFIX_PATH=/ros\0PYTHONPATH=/ros/python\0SHLVL=2\0'
        with patch.object(module.subprocess, 'check_output', return_value=raw) as call:
            first = module.helper_environment(time.monotonic() + 10)
            with patch.dict(os.environ, {'REPORT_TEST_CURRENT': 'new'}):
                second = module.helper_environment(time.monotonic() + 10)
            self.assertEqual(first['PYTHONPATH'], '/ros/python')
            self.assertEqual(second['REPORT_TEST_CURRENT'], 'new')
            self.assertNotIn('SHLVL', module._overlay)
            call.assert_called_once()

    def test_failure_is_not_cached(self):
        raw = b'AMENT_PREFIX_PATH=/ros\0PYTHONPATH=/ros/python\0'
        with patch.object(module.subprocess, 'check_output', side_effect=[OSError(), raw]) as call:
            self.assertIsNone(module.helper_environment(time.monotonic() + 10))
            self.assertIsNotNone(module.helper_environment(time.monotonic() + 10))
            self.assertEqual(call.call_count, 2)

    def test_invalid_environment_falls_back(self):
        with patch.object(module.subprocess, 'check_output', return_value=b'PATH=/bin\0'):
            self.assertIsNone(module.helper_environment(time.monotonic() + 10))
            self.assertIsNone(module._overlay)

    def test_expired_deadline_does_not_launch_shell(self):
        with patch.object(module.subprocess, 'check_output') as call:
            self.assertIsNone(module.helper_environment(time.monotonic() - 1))
            call.assert_not_called()

    def test_capture_timeout_uses_remaining_budget(self):
        with patch.object(module.subprocess, 'check_output', side_effect=module.subprocess.TimeoutExpired('bash', .5)) as call:
            self.assertIsNone(module.helper_environment(time.monotonic() + .5))
            self.assertLessEqual(call.call_args.kwargs['timeout'], .5)

