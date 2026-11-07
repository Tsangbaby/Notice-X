#!/usr/bin/env python3
"""Bind exact source/run, retained original DEB and raw evidence without rebuilding.

scope/retain/manifest are CI producers. verify is a read-only offline checksum and
identity check; callers must independently obtain the expected SHA/run/attempt
from GitHub. Checksums bind bytes, not publisher trust or device compatibility.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import posixpath
import subprocess
import sys

from verify_package import IDENTITY, parse_control

IDENTIFIERS = ("source_sha", "repository", "run_id", "attempt", "scheme")
REPOSITORY = "Tsangbaby/Notice-X"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def source_identity(env):
    result = {"source_sha": env["GITHUB_SHA"], "repository": env["GITHUB_REPOSITORY"],
              "run_id": env["GITHUB_RUN_ID"], "attempt": env["GITHUB_RUN_ATTEMPT"], "scheme": "roothide"}
    assert re.fullmatch(r"[0-9a-f]{40}", result["source_sha"]), "invalid source SHA"
    assert result["repository"] == REPOSITORY, "wrong canonical repository"
    assert re.fullmatch(r"[1-9][0-9]*", result["run_id"]), "invalid run ID"
    assert re.fullmatch(r"[1-9][0-9]*", result["attempt"]), "invalid attempt"
    return result


def make_graph(root):
    graph = {}
    for path, target in (("Makefile", "NoticeX"), ("prefs/Makefile", "NoticeXPrefs")):
        raw = (root / path).read_text().replace("\\\n", " ")
        found = re.findall(r"^" + re.escape(target) + r"_FILES\s*=\s*(.*)$", raw, re.M)
        assert len(found) == 1, "ambiguous compile graph"
        files = []
        for item in found[0].split():
            resolved = (root / path).parent.joinpath(item).resolve()
            relative = str(resolved.relative_to(root.resolve()))
            assert resolved.is_file(), ("missing shipped source", relative)
            files.append({"path": relative, "sha256": sha(resolved)})
        graph[target] = {"architectures": ["arm64", "arm64e"], "minimum_ios": "15.0", "sources": files}
    return graph


def scope(root, out):
    out.mkdir(parents=True, exist_ok=True)
    identity = source_identity(os.environ)
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    assert head == identity["source_sha"], "checkout HEAD does not match workflow source"
    subprocess.run(["git", "-C", str(root), "diff", "--quiet", "HEAD"], check=True)
    subprocess.run(["git", "-C", str(root), "diff", "--cached", "--quiet"], check=True)
    fields = parse_control((root / "control").read_bytes())
    assert all(fields.get(key) == value for key, value in IDENTITY.items()), "wrong source package metadata"
    result = {**identity, "package": fields, "compile_graph": make_graph(root),
              "theos_commit": os.environ["THEOS_COMMIT"], "device_tested": False,
              "simulator_executed": False, "kind": "candidate_build_not_device_acceptance"}
    (out / "SOURCE_COMMIT.txt").write_text(head + "\n")
    (out / "SOURCE_REPOSITORY.txt").write_text(identity["repository"] + "\n")
    write_json(out / "scope.json", result)
    return result


def retain(root, out):
    fields = parse_control((root / "control").read_bytes())
    name = "{Package}_{Version}_{Architecture}.deb".format(**fields)
    packages = sorted((root / "packages").glob("*.deb"))
    assert len(packages) == 1 and packages[0].name == name, ("not exactly one expected original DEB", packages)
    path = packages[0]
    assert path.is_file() and not path.is_symlink(), "invalid original package"
    scope_data = json.loads((out / "scope.json").read_text())
    log = out / "theos-build.log"
    assert log.is_file() and log.stat().st_size > 0, "missing complete build log"
    target = out / name
    # Never mutate/repack a package to satisfy the verifier. Existing bytes must match.
    raw = path.read_bytes()
    if target.exists():
        assert target.read_bytes() == raw, "refusing to replace retained original"
    else:
        with target.open("xb") as stream:
            stream.write(raw)
    assert target.read_bytes() == raw, "original copy mismatch"
    result = {**{key: scope_data[key] for key in IDENTIFIERS}, "package": name, "bytes": len(raw),
              "sha256": sha(target), "build_log_sha256": sha(log), "verified": False,
              "note": "retained before package checks; not yet a deliverable"}
    write_json(out / "original-package.json", result)
    return result


def evidence_files(out):
    paths = []
    for path in sorted(out.rglob("*")):
        assert not path.is_symlink(), "symlink in evidence directory"
        if path.is_file() and path.name not in ("evidence-manifest.json", "SHA256SUMS.txt"):
            paths.append(path)
    return paths


def verify_compile_log(raw, graph):
    """Reconcile verbose *commands* with the frozen target/source/arch graph.

    Commands are enabled with MESSAGES=1. Swift diagnostic text is deliberately
    not an input protocol. Link/sign labels are from the pinned messages.mk.
    These are build invocation/completion evidence, not runtime correctness.
    """
    raw = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    seen = set()
    for line in raw.splitlines():
        try:
            tokens = shlex.split(line)
        except ValueError:
            continue  # diagnostics may contain unmatched quotes; not commands
        compilers = [Path(token).name for token in tokens]
        if "-c" not in tokens or not any(name in ("swiftc", "clang") for name in compilers):
            continue
        if "-target" not in tokens:
            continue
        index = tokens.index("-target")
        if index + 1 >= len(tokens):
            continue
        match = re.fullmatch(r"(arm64e|arm64)-apple-ios15(?:\.0(?:\.0)?)?", tokens[index + 1])
        if match is None:
            continue
        arch = match[1]
        if "swiftc" in compilers and "-emit-module-path" in tokens:
            index = tokens.index("-emit-module-path")
            target = Path(tokens[index + 1]).stem if index + 1 < len(tokens) else None
        else:
            defines = [token.split("=", 1)[1].strip('"') for token in tokens if token.startswith("-DTHEOS_INSTANCE_NAME=")]
            target = defines[0] if len(defines) == 1 else None
        if target not in graph:
            continue
        prefix = "prefs/" if target == "NoticeXPrefs" else ""
        for token in tokens:
            if token.endswith((".swift", ".m")):
                relative = posixpath.normpath(prefix + token)
                seen.add((target, relative, arch))
    expected = {(target, entry["path"], arch) for target, value in graph.items()
                for entry in value["sources"] for arch in value["architectures"]}
    assert expected <= seen, ("missing target/source/architecture compile evidence", sorted(expected - seen))
    links = []
    for target, value in graph.items():
        kind = "tweak" if target == "NoticeX" else "bundle"
        for arch in value["architectures"]:
            pattern = r"^==> Linking " + kind + " " + re.escape(target) + r" \(" + re.escape(arch) + r"\)(?:\.\.\.|…)\s*$"
            assert re.search(pattern, raw, re.M), ("missing target/architecture link evidence", target, arch)
            links.append([target, arch])
        assert re.search(r"^==> Signing " + re.escape(target) + r"(?:\.\.\.|…)\s*$", raw, re.M), ("missing signing evidence", target)
    return {"compile_entries": [list(row) for row in sorted(expected)], "link_entries": links,
            "signed_targets": sorted(graph), "evidence": "verbose_commands_and_pinned_theos_labels"}


def manifest(out, job_status):
    try:
        return _manifest(out, job_status)
    except (AssertionError, OSError, ValueError, KeyError) as error:
        # A failed evidence reader must not lose the original package or logs.
        # Save an explicitly failed snapshot before preserving the fatal status.
        result = _manifest(out, "failure")
        result["validation_error"] = str(error)
        write_json(out / "evidence-manifest.json", result)
        records = {name: entry["sha256"] for name, entry in result["files"].items()}
        records["evidence-manifest.json"] = sha(out / "evidence-manifest.json")
        (out / "SHA256SUMS.txt").write_text("".join(records[name] + "  " + name + "\n" for name in sorted(records)))
        raise


def _manifest(out, job_status):
    assert job_status in ("success", "failure", "cancelled", "skipped"), "unknown job status"
    scope_path = out / "scope.json"
    scope_data = json.loads(scope_path.read_text()) if scope_path.is_file() else {}
    if job_status == "success":
        for name in ("source-tests.log", "swift-tests.log", "theos-build.log", "package-verification.log",
                     "package-verification.json", "original-package.json", "SOURCE_COMMIT.txt", "SOURCE_REPOSITORY.txt"):
            path = out / name
            assert path.is_file() and path.stat().st_size > 0, ("missing successful gate evidence", name)
        original = json.loads((out / "original-package.json").read_text())
        report = json.loads((out / "package-verification.json").read_text())
        assert report["sha256"] == original["sha256"] == sha(out / original["package"]), "verified package checksum mismatch"
        assert report["device_tested"] is False and report["scheme"] == "roothide", "incorrect package evidence scope"
        swift = json.loads((out / "swift-tests/swift-tests.json").read_text())
        assert swift["executed"] is True and type(swift["assertions"]) is int and swift["assertions"] > 0, "Swift tests did not execute"
        log = (out / "swift-tests/swift-core.log").read_text()
        assert re.fullmatch(r"NOTICE_X_CORE_PASS assertions=" + str(swift["assertions"]) + r"\n", log), "Swift report/log count mismatch"
        assert swift["device_tested"] is False, "host replay is not device proof"
        compiled = verify_compile_log((out / "theos-build.log").read_text(), scope_data["compile_graph"])
        write_json(out / "compile-verification.json", compiled)
    files = {str(path.relative_to(out)): {"sha256": sha(path), "bytes": path.stat().st_size}
             for path in evidence_files(out)}
    result = {"identity": {key: scope_data.get(key) for key in IDENTIFIERS},
              "job_status_before_upload": job_status, "device_tested": False, "files": files,
              "evidence": "checksums_not_signer_trust_or_device_acceptance"}
    write_json(out / "evidence-manifest.json", result)
    checksums = [(entry["sha256"], name) for name, entry in files.items()]
    checksums.append((sha(out / "evidence-manifest.json"), "evidence-manifest.json"))
    (out / "SHA256SUMS.txt").write_text("".join(digest + "  " + name + "\n" for digest, name in sorted(checksums, key=lambda row: row[1])))
    return result


def verify_evidence(out, expected):
    data = json.loads((out / "evidence-manifest.json").read_text())
    assert all(data["identity"].get(key) == expected[key] for key in IDENTIFIERS), "evidence source/run identity mismatch"
    files = {str(path.relative_to(out)): path for path in evidence_files(out)}
    assert files.keys() == data["files"].keys(), "evidence inventory mismatch"
    for name, path in files.items():
        record = data["files"][name]
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], ("evidence checksum mismatch", name)
    for key in ("source_sha", "repository"):
        filename = "SOURCE_COMMIT.txt" if key == "source_sha" else "SOURCE_REPOSITORY.txt"
        assert (out / filename).read_text() == expected[key] + "\n", "source marker mismatch"
    scope_data = json.loads((out / "scope.json").read_text())
    assert all(scope_data.get(key) == expected[key] for key in IDENTIFIERS), "scope source/run identity mismatch"
    checksum_lines = []
    for name, record in sorted(data["files"].items()):
        checksum_lines.append(record["sha256"] + "  " + name + "\n")
    checksum_lines.append(sha(out / "evidence-manifest.json") + "  evidence-manifest.json\n")
    assert sorted((out / "SHA256SUMS.txt").read_text().splitlines(keepends=True)) == sorted(checksum_lines), "checksum manifest mismatch"
    original_path = out / "original-package.json"
    if original_path.is_file():
        original = json.loads(original_path.read_text())
        assert all(original[key] == expected[key] for key in IDENTIFIERS), "original package identity mismatch"
        assert sha(out / original["package"]) == original["sha256"], "original package checksum mismatch"
        assert sha(out / "theos-build.log") == original["build_log_sha256"], "original compiler log checksum mismatch"
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("scope", "retain", "manifest", "verify"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--job-status", default="failure")
    parser.add_argument("--source-sha")
    parser.add_argument("--repository", default=REPOSITORY)
    parser.add_argument("--run-id")
    parser.add_argument("--attempt")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        if not __debug__:
            raise RuntimeError("Run without -O: assertions are required")
        if args.action == "scope":
            result = scope(root, args.out)
        elif args.action == "retain":
            result = retain(root, args.out)
        elif args.action == "manifest":
            result = manifest(args.out, args.job_status)
        else:
            expected = source_identity({"GITHUB_SHA": args.source_sha or "", "GITHUB_REPOSITORY": args.repository,
                                        "GITHUB_RUN_ID": args.run_id or "", "GITHUB_RUN_ATTEMPT": args.attempt or ""})
            result = verify_evidence(args.out, expected)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (AssertionError, RuntimeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
