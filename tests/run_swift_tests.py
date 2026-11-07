#!/usr/bin/env python3
"""Execute real portable Swift owners; not UIKit or SpringBoard device proof."""
from pathlib import Path
import argparse
import json
import os
import re
import shutil
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    out=args.out
    out.mkdir(parents=True,exist_ok=True)
    compiler=os.environ.get('NOTICE_SWIFTC') or shutil.which('swiftc')
    sdk=[]
    if sys.platform=='darwin':
        compiler=compiler or subprocess.check_output(['xcrun','--find','swiftc'],text=True).strip()
        sdk=['-sdk',subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip()]
    if not compiler:
        raise SystemExit('Swift compiler required: this gate must execute, not skip')
    sources=[root/'Sources/Core/NoticePolicy.swift',root/'tests/Core/main.swift']
    binary=out/'notice-core-host'
    command=[compiler,'-swift-version','5','-O',*sdk,*map(str,sources),'-o',str(binary)]
    build=subprocess.run(command,capture_output=True,text=True,timeout=120)
    (out/'swift-core-compile.log').write_text(build.stdout+build.stderr)
    print(build.stdout+build.stderr,end='',flush=True)
    if build.returncode:raise SystemExit(build.returncode)
    run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=30)
    (out/'swift-core.log').write_text(run.stdout+run.stderr)
    print(run.stdout+run.stderr,end='',flush=True)
    if run.returncode:raise SystemExit(run.returncode)
    match=re.fullmatch(r'NOTICE_X_CORE_PASS assertions=([1-9][0-9]*)\n',run.stdout)
    if not match or run.stderr:raise SystemExit('invalid Swift execution completion')
    (out/'swift-tests.json').write_text(json.dumps({'executed':True,'assertions':int(match[1]),'kind':'portable_swift_execution','device_tested':False},indent=2)+'\n')
    if sys.platform=='darwin':
        from run_native_tests import run_native
        from run_runtime_tests import run_runtime
        run_native(root,out)
        run_runtime(root,out,compiler,sdk)

if __name__=='__main__':main()
