#!/usr/bin/env python3
"""Portable runner-contract checks only; synthetic process results are not Swift execution."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('visual_runner', ROOT / 'tests/run_visual_tests.py')
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class RunnerContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / 'result'

    def replay(self, negative=None, candidate=None, compile_error=False):
        negative = negative if negative is not None else subprocess.CompletedProcess(
            [], 1, '', RUNNER.EXPECTED_RED)
        candidate = candidate if candidate is not None else subprocess.CompletedProcess(
            [], 0, 'NOTICE_X_VISUAL_PASS assertions=42\n', '')
        commands = []

        def command(args, log, **kwargs):
            if args[0] == 'git':
                # Deliberately synthetic source for Python plumbing only; never a visual report artifact.
                return subprocess.CompletedProcess(args, 0, '// synthetic runner unit input\n', '')
            return negative if 'beta2-negative' in args[0] else candidate

        def compile_command(args, log, label):
            commands.append(args)
            if compile_error:
                raise RuntimeError('synthetic missing double API compile failure')

        with patch.object(RUNNER.sys, 'platform', 'darwin'), \
                patch.object(RUNNER, '_command', side_effect=command), \
                patch.object(RUNNER, '_compile', side_effect=compile_command), \
                redirect_stdout(io.StringIO()):
            report = RUNNER.run_visual(ROOT, self.out, 'synthetic-swiftc', ['-sdk', 'synthetic-sdk'])
        return report, commands

    def test_unsupported_host_fails_closed(self):
        with patch.object(RUNNER.sys, 'platform', 'linux'):
            with self.assertRaisesRegex(RuntimeError, 'macOS host required'):
                RUNNER.run_visual(ROOT, self.out, 'unused', [])
        self.assertFalse((self.out / 'visual-tests.json').exists())

    def test_synthetic_report_contract_and_exact_production_source_command(self):
        report, commands = self.replay()
        self.assertEqual(report['kind'], 'production_swift_uikit_double_replay')
        self.assertTrue(report['executed'])
        self.assertEqual(report['assertions'], 42)
        self.assertFalse(report['device_tested'])
        self.assertTrue(report['baseline']['expected_red'])
        self.assertEqual(len(commands), 3)
        self.assertIn(str(ROOT / RUNNER.ANIMATOR), commands[-1])
        self.assertIn(str(ROOT / 'Sources/Core/NoticePolicy.swift'), commands[-1])
        self.assertEqual(json.loads((self.out / 'visual-tests.json').read_text()), report)

    def test_compile_failure_is_not_expected_red(self):
        with self.assertRaisesRegex(RuntimeError, 'compile failure'):
            self.replay(compile_error=True)
        self.assertFalse((self.out / 'visual-tests.json').exists())

    def test_crash_is_not_expected_red_even_with_expected_message(self):
        with self.assertRaisesRegex(AssertionError, 'beta2 must compile'):
            self.replay(negative=subprocess.CompletedProcess([], -11, '', RUNNER.EXPECTED_RED))
        self.assertFalse((self.out / 'visual-tests.json').exists())

    def test_wrong_baseline_assertion_is_not_expected_red(self):
        with self.assertRaisesRegex(AssertionError, 'beta2 must compile'):
            self.replay(negative=subprocess.CompletedProcess([], 1, '',
                'NOTICE_X_VISUAL_FAIL case=prepare assertion=other\n'))
        self.assertFalse((self.out / 'visual-tests.json').exists())

    def test_candidate_failed_exit_with_pass_marker_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'candidate visual execution failed'):
            self.replay(candidate=subprocess.CompletedProcess([], 1,
                'NOTICE_X_VISUAL_PASS assertions=42\n', ''))
        self.assertFalse((self.out / 'visual-tests.json').exists())

    def test_candidate_noise_or_zero_assertions_is_rejected(self):
        for stdout, stderr in [('NOTICE_X_VISUAL_PASS assertions=42\n', 'warning'),
                               ('NOTICE_X_VISUAL_PASS assertions=0\n', ''),
                               ('NOTICE_X_VISUAL_PASS assertions=42\nextra\n', '')]:
            with self.subTest(stdout=stdout, stderr=stderr):
                with self.assertRaisesRegex(AssertionError, 'candidate visual execution failed'):
                    self.replay(candidate=subprocess.CompletedProcess([], 0, stdout, stderr))
                self.assertFalse((self.out / 'visual-tests.json').exists())


if __name__ == '__main__':
    unittest.main()
