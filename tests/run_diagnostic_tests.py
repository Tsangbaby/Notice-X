#!/usr/bin/env python3
"""Execute the real bounded diagnostic producer; Foundation host, not device proof."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess


def run_diagnostic(root: Path, out: Path):
    binary = out / "notice-diagnostic-host"
    command = ["xcrun", "clang", "-fobjc-arc", "-fblocks", "-Wall", "-Wextra", "-Werror",
               "-DNX_DIAGNOSTIC_HOST_TEST=1", "-framework", "Foundation", "-framework", "CoreFoundation",
               str(root / "Sources/Native/NoticeXDiagnostics.m"),
               str(root / "tests/Diagnostics/diagnostic_host.m"), "-o", str(binary)]
    built = subprocess.run(command, capture_output=True, text=True, timeout=90)
    (out / "diagnostic-compile.log").write_text(built.stdout + built.stderr)
    print(built.stdout + built.stderr, end="", flush=True)
    if built.returncode:
        raise SystemExit(built.returncode)
    counts = {}
    for mode in ("healthy", "reset-failure", "write-failure"):
        target = out / ("diagnostic-" + mode + ".plist")
        result = subprocess.run([str(binary), mode, str(target)], capture_output=True, text=True, timeout=30)
        (out / ("diagnostic-" + mode + ".log")).write_text(result.stdout + result.stderr)
        print(result.stdout + result.stderr, end="", flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
        match = re.fullmatch(r"NOTICE_X_DIAGNOSTIC_PASS assertions=([1-9][0-9]*)\n", result.stdout)
        if not match or result.stderr:
            raise AssertionError("diagnostic host completion mismatch")
        counts[mode] = int(match[1])
    spec = importlib.util.spec_from_file_location("nx_diagnostic_reader", root / "tools/read_diagnostic.py")
    assert spec is not None and spec.loader is not None
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    snapshot = reader.validate((out / "diagnostic-healthy.plist").read_bytes())
    assert set(snapshot["trace"]) == reader.ALLOWED_PHASES, "burst lost a first-reach phase"
    assert type(snapshot["resetConfirmed"]) is bool and snapshot["resetConfirmed"] is True
    report = {"kind": "real_foundation_diagnostic_producer_and_strict_binary_plist_decode",
              "assertions": counts, "validated_phase_count": snapshot["sequence"],
              "serialized_bytes": (out / "diagnostic-healthy.plist").stat().st_size,
              "device_tested": False}
    (out / "diagnostic-tests.json").write_text(json.dumps(report, indent=2) + "\n")
