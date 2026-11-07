#!/usr/bin/env python3
"""Execute unchanged Swift Hook bodies against an explicit Objective-C predecessor fixture."""
from pathlib import Path
import json
import re
import subprocess


def run_runtime(root:Path,out:Path,compiler:str,sdk:list[str]):
    raw=(root/'Sources/Runtime/NoticeRuntime.swift').read_text()
    bindings={'SBNotificationPresentableViewController':'NXRuntimeFixturePresentable',
              'NCNotificationPresentableViewController':'NXRuntimeFixtureAbsent'}
    source=raw
    for old,new in bindings.items():
        literal='"'+old+'"'
        if source.count(literal)!=1:raise AssertionError(('runtime fixture binding',old))
        source=source.replace(literal,'"'+new+'"',1)
    inverse=source
    for old,new in bindings.items():inverse=inverse.replace('"'+new+'"','"'+old+'"',1)
    if inverse!=raw:raise AssertionError('runtime bodies changed in fixture')
    path=out/'NoticeRuntimeHost.swift';path.write_text(source)
    counts={}
    for mode,flag in [('healthy','0'),('wrong-abi','1')]:
        obj=out/('runtime-'+mode+'.o')
        c=['xcrun','clang','-fobjc-arc','-fblocks','-Wall','-Wextra','-Werror','-DNX_WRONG_ABI='+flag,
           '-c',str(root/'tests/Runtime/runtime_fixture.m'),'-o',str(obj)]
        binary=out/('notice-runtime-'+mode)
        s=[compiler,'-swift-version','5','-O',*sdk,'-import-objc-header',str(root/'tests/Runtime/RuntimeBridge.h'),
           str(path),str(root/'Sources/Support/NoticeDiagnostics.swift'),
           str(root/'tests/Runtime/main.swift'),str(obj),'-o',str(binary)]
        for label,command in [('native',c),('swift',s)]:
            result=subprocess.run(command,capture_output=True,text=True,timeout=120)
            (out/('runtime-'+mode+'-'+label+'-compile.log')).write_text(result.stdout+result.stderr)
            print(result.stdout+result.stderr,end='',flush=True)
            if result.returncode:raise SystemExit(result.returncode)
        result=subprocess.run([str(binary),mode],capture_output=True,text=True,timeout=25)
        (out/('runtime-'+mode+'.log')).write_text(result.stdout+result.stderr)
        print(result.stdout+result.stderr,end='',flush=True)
        if result.returncode:raise SystemExit(result.returncode)
        match=re.fullmatch(r'NOTICE_X_RUNTIME_PASS mode='+re.escape(mode)+r' assertions=([1-9][0-9]*)\n',result.stdout)
        if not match or result.stderr:raise AssertionError('runtime fixture completion mismatch')
        counts[mode]=int(match[1])
    (out/'runtime-tests.json').write_text(json.dumps({'kind':'actual_swift_hook_with_objc_runtime_fixture','assertions':counts,'device_tested':False},indent=2)+'\n')
