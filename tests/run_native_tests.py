#!/usr/bin/env python3
"""Run actual native ABI provider with explicitly rebound Foundation fixtures."""
from pathlib import Path
import json
import re
import subprocess


def run_native(root:Path,out:Path):
    source=root/'Sources/Native/NoticeXBootstrap.m'
    raw=source.read_text()
    bindings={'NCNotificationPresentableViewController':'NXFixturePresentable',
              'NCNotificationShortLookViewController':'NXFixtureShortController',
              'NCNotificationShortLookView':'NXFixtureLook',
              'SBLockScreenManager':'NXFixtureLockManager',
              'SBCoverSheetPresentationManager':'NXFixtureCoverManager'}
    rebound=raw
    for old,new in bindings.items():
        literal='@"'+old+'"'
        if rebound.count(literal)!=1:raise AssertionError(('private fixture binding not unique',old))
        rebound=rebound.replace(literal,'@"'+new+'"',1)
    inverse=rebound
    for old,new in bindings.items():inverse=inverse.replace('@"'+new+'"','@"'+old+'"',1)
    if inverse!=raw:raise AssertionError('provider bodies changed in fixture')
    path=out/'NativeProviderFixture.m'
    path.write_text(rebound)
    binary=out/'notice-native-host'
    command=['xcrun','clang','-fobjc-arc','-fblocks','-Wall','-Wextra','-Werror',
             '-framework','Foundation','-I'+str(root/'tests/Native/include'),
             '-I'+str(root/'Sources/Native'),str(path),str(root/'tests/Native/native_host.m'),'-o',str(binary)]
    built=subprocess.run(command,capture_output=True,text=True,timeout=90)
    (out/'native-compile.log').write_text(built.stdout+built.stderr)
    print(built.stdout+built.stderr,end='',flush=True)
    if built.returncode:raise SystemExit(built.returncode)
    result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=30)
    (out/'native-host.log').write_text(result.stdout+result.stderr)
    print(result.stdout+result.stderr,end='',flush=True)
    if result.returncode:raise SystemExit(result.returncode)
    match=re.fullmatch(r'NOTICE_X_NATIVE_PASS assertions=([1-9][0-9]*)\n',result.stdout)
    if not match or result.stderr:raise AssertionError('invalid native completion')
    (out/'native-tests.json').write_text(json.dumps({'kind':'foundation_native_fixture','assertions':int(match[1]),'device_tested':False},indent=2)+'\n')
