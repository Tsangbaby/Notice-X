#!/usr/bin/env python3
"""macOS replay of exact NXCardAnimator Swift with explicit, non-rendering UIKit doubles."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys


BASELINE = '8328ac1720189a4eb382cf1495712fcec004394e'
ANIMATOR = Path('Sources/UI/NoticeCardAnimator.swift')
EXPECTED_RED = 'NOTICE_X_VISUAL_FAIL case=prepare assertion=no-native-mask\n'
CASES = 8


def _command(command, log, *, timeout=120, cwd=None, env=None):
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                            cwd=cwd, env=env)
    log.write_text(result.stdout + result.stderr)
    return result


def _compile(command, log, label):
    result = _command(command, log)
    print(result.stdout + result.stderr, end='', flush=True)
    if result.returncode:
        # A missing double API, compiler error or link error is never behavioral RED.
        raise RuntimeError(f'{label} compile/link failed ({result.returncode}); see {log}')


def run_visual(root: Path, out: Path, compiler: str, sdk: list[str]):
    """Parent integration API. Fail closed unless both real executables are exercised.

    `sdk` is the same argument list accepted by run_runtime, normally ['-sdk', path].
    Writes module/binaries/logs below out/visual-host and out/visual-tests.json.
    Returns the JSON report after candidate PASS and frozen predecessor EXPECTED_RED.
    """
    if sys.platform != 'darwin':
        raise RuntimeError('macOS host required: real Foundation/CoreGraphics replay must execute, not skip')
    root, out = Path(root).resolve(), Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / 'visual-tests.json'
    report_path.unlink(missing_ok=True)
    host = out / 'visual-host'
    host.mkdir(parents=True, exist_ok=True)
    fixture = root / 'tests/Visual'
    actual = root / ANIMATOR
    original = actual.read_bytes()
    core = root / 'Sources/Core/NoticePolicy.swift'
    core_bytes = core.read_bytes()
    baseline = _command(['git', 'show', f'{BASELINE}:{ANIMATOR.as_posix()}'],
                        host / 'baseline-source.log', cwd=root)
    if baseline.returncode or not baseline.stdout:
        raise RuntimeError(f'frozen beta2 source unavailable: {BASELINE}:{ANIMATOR}')
    predecessor = host / 'NoticeCardAnimator-beta2.swift'
    predecessor.write_text(baseline.stdout)
    common = [compiler, '-swift-version', '5', '-O', *sdk]
    _compile([*common, '-emit-library', '-emit-module', '-module-name', 'UIKit',
              '-emit-module-path', str(host / 'UIKit.swiftmodule'),
              str(fixture / 'UIKit.swift'), '-o', str(host / 'libUIKit.dylib')],
             host / 'uikit-double-compile.log', 'explicit UIKit double')

    environment = os.environ.copy()
    environment['DYLD_LIBRARY_PATH'] = str(host) + (
        os.pathsep + environment['DYLD_LIBRARY_PATH'] if environment.get('DYLD_LIBRARY_PATH') else '')
    counts = None
    for mode, source in [('beta2-negative', predecessor), ('candidate', actual)]:
        binary = host / f'notice-visual-{mode}'
        _compile([*common, '-I', str(host), '-L', str(host), '-lUIKit',
                  '-Xlinker', '-rpath', '-Xlinker', str(host),
                  str(core), str(source), str(fixture / 'main.swift'), '-o', str(binary)],
                 host / f'{mode}-compile.log', mode)
        result = _command([str(binary)], host / f'{mode}.log', timeout=30, env=environment)
        print(result.stdout + result.stderr, end='', flush=True)
        if mode == 'beta2-negative':
            if result.returncode != 1 or result.stdout or result.stderr != EXPECTED_RED:
                raise AssertionError('beta2 must compile and reach exactly prepare/no-native-mask; '
                                     'a crash or fixture error is not expected behavioral RED')
            print('NOTICE_X_VISUAL_EXPECTED_RED baseline=8328ac1 assertion=no-native-mask', flush=True)
        else:
            match = re.fullmatch(r'NOTICE_X_VISUAL_PASS assertions=([1-9][0-9]*)\n',
                                 result.stdout)
            if result.returncode or result.stderr or not match:
                raise AssertionError(f'candidate visual execution failed; see {host / "candidate.log"}')
            counts = {'cases': CASES, 'assertions': int(match[1])}
    if actual.read_bytes() != original or core.read_bytes() != core_bytes:
        raise AssertionError('production source changed during replay; rerun against a stable source')
    report = {
        'executed': True,
        'kind': 'production_swift_uikit_double_replay',
        **counts,
        'animator_sha256': hashlib.sha256(original).hexdigest(),
        'core_sha256': hashlib.sha256(core_bytes).hexdigest(),
        'baseline': {'commit': BASELINE, 'compiled': True, 'expected_red': True,
                     'assertion': 'prepare/no-native-mask',
                     'sha256': hashlib.sha256(baseline.stdout.encode()).hexdigest()},
        'device_tested': False,
        'uikit_rendering_tested': False,
        'limits': 'Deterministic host state/geometry/resource replay; not UIKit scheduling, '
                  'notification pixels, blur rendering, native ingress coordination or handset timing proof.',
    }
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--swiftc', help='Swift compiler; otherwise NOTICE_SWIFTC, PATH, then xcrun')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        raise SystemExit('macOS host required: no skipped or simulated visual PASS')
    compiler = args.swiftc or os.environ.get('NOTICE_SWIFTC') or shutil.which('swiftc')
    if not compiler:
        compiler = subprocess.check_output(['xcrun', '--find', 'swiftc'], text=True).strip()
    sdk = ['-sdk', subprocess.check_output(
        ['xcrun', '--sdk', 'macosx', '--show-sdk-path'], text=True).strip()]
    run_visual(Path(__file__).resolve().parents[1], args.out, compiler, sdk)


if __name__ == '__main__':
    main()
