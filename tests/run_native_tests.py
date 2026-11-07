#!/usr/bin/env python3
"""Execute production native ABI/admission bodies with explicit public/private hosts."""
from pathlib import Path
import json
import re
import subprocess


def run_native(root: Path, out: Path):
    raw = (root / 'Sources/Native/NoticeXBootstrap.m').read_text()
    bindings = {'NCNotificationPresentableViewController': 'NXFixturePresentable',
                'NCNotificationShortLookViewController': 'NXFixtureShortController',
                'NCNotificationShortLookView': 'NXFixtureLook',
                'SBLockScreenManager': 'NXFixtureLockManager',
                'SBCoverSheetPresentationManager': 'NXFixtureCoverManager'}
    rebound = raw
    for old, new in bindings.items():
        literal = '@"' + old + '"'
        if rebound.count(literal) != 1:
            raise AssertionError(('private fixture binding not unique', old))
        rebound = rebound.replace(literal, '@"' + new + '"', 1)
    os_read = 'NSProcessInfo.processInfo.operatingSystemVersion'
    os_host = 'NXFixtureProcessInfo.processInfo.operatingSystemVersion'
    if rebound.count(os_read) != 1:
        raise AssertionError('public OS binding not unique')
    rebound = rebound.replace(os_read, os_host, 1)
    inverse = rebound.replace(os_host, os_read, 1)
    for old, new in bindings.items():
        inverse = inverse.replace('@"' + new + '"', '@"' + old + '"', 1)
    if inverse != raw:
        raise AssertionError('production provider bodies changed in fixture')

    def compile_host(source, name):
        path = out / (name + '.m')
        path.write_text(source)
        binary = out / name
        command = ['xcrun', 'clang', '-fobjc-arc', '-fblocks', '-Wall', '-Wextra', '-Werror',
                   '-framework', 'Foundation', '-I' + str(root / 'tests/Native/include'),
                   '-I' + str(root / 'Sources/Native'), '-I' + str(root / 'tests/Native'),
                   '-include', str(root / 'tests/Native/OSFixture.h'),
                   str(path), str(root / 'tests/Native/native_host.m'), '-o', str(binary)]
        built = subprocess.run(command, capture_output=True, text=True, timeout=90)
        (out / (name + '-compile.log')).write_text(built.stdout + built.stderr)
        print(built.stdout + built.stderr, end='', flush=True)
        if built.returncode:
            raise SystemExit(built.returncode)
        return binary

    binary = compile_host(rebound, 'notice-native-host')
    counts = {}
    for lane in ('15.4.1', '15.4.0', '16.0.3'):
        result = subprocess.run([str(binary), lane], capture_output=True, text=True, timeout=30)
        (out / ('native-host-' + lane + '.log')).write_text(result.stdout + result.stderr)
        print(result.stdout + result.stderr, end='', flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
        match = re.fullmatch(r'NOTICE_X_NATIVE_PASS assertions=([1-9][0-9]*)\n', result.stdout)
        if not match or result.stderr:
            raise AssertionError('invalid native completion')
        counts[lane] = int(match[1])
    # Restore the rejected look predicate without altering the other production
    # bodies. Require a successful compilation, then the exact behavioral failure.
    gate = 'if (!NXLifecycleOwnsBannerIdentity())'
    if rebound.count(gate) != 1:
        raise AssertionError('negative-control anchor not unique')
    mutant = rebound.replace(gate, 'if (NXLifecycleOwnsBannerIdentity() || !NXLifecycleOwnsBannerIdentity())', 1)
    negative = compile_host(mutant, 'notice-native-restored-look-filter')
    rejected = subprocess.run([str(negative), '15.4.1'], capture_output=True, text=True, timeout=30)
    (out / 'native-negative-control.log').write_text(rejected.stdout + rejected.stderr)
    expected = 'NOTICE_X_NATIVE_FAIL: lifecycle admits target banner when look flag is false\n'
    if rejected.returncode != 1 or rejected.stdout or rejected.stderr != expected:
        raise AssertionError('restored look filter did not fail the intended device-state assertion')
    print('NOTICE_X_NATIVE_NEGATIVE_CONTROL_PASS restored_look_filter_rejected_target_banner', flush=True)
    report = {'kind': 'foundation_native_fixture', 'assertions': sum(counts.values()),
              'os_lanes': counts, 'negative_control': 'restored_look_filter_rejected_target_banner',
              'device_tested': False}
    (out / 'native-tests.json').write_text(json.dumps(report, indent=2) + '\n')
