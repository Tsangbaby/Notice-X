#!/usr/bin/env python3
"""Independently inspect an ORIGINAL Notice-X RootHide .deb, never install/repack.

Usage: python3 -B tools/verify_package.py ORIGINAL.deb --report report.json
Requires dpkg-deb and Python stdlib only. No source checkout or tests required.
Checks all shipped Mach-O slices, signatures/code-page hashes, device deployment,
Swift code symbols, control metadata, safe payload inventory and Settings resources.
Structural signatures are NOT signer trust, device acceptance or reproducibility.
"""
import argparse
import bz2
import gzip
import hashlib
import io
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import struct
import subprocess
import sys
import tarfile
import tempfile
from xml.parsers.expat import ExpatError

from verify_macho import verify_macho

MAX_INPUT = 64 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
MAX_MEMBERS = 2000
LZMA_MEMORY = 128 * 1024 * 1024
TWEAK = "Library/MobileSubstrate/DynamicLibraries/NoticeX.dylib"
FILTER = "Library/MobileSubstrate/DynamicLibraries/NoticeX.plist"
BUNDLE = "Library/PreferenceBundles/NoticeXPrefs.bundle/"
LOADER = "Library/PreferenceLoader/Preferences/NoticeX.plist"
IDENTITY = {"Package": "com.tsangbaby.noticex", "Name": "Notice-X",
            "Version": "0.1.0-beta1", "Architecture": "iphoneos-arm64e",
            "Author": "Tsangbaby", "Maintainer": "Tsangbaby"}
DEPENDENCIES = "mobilesubstrate, preferenceloader, firmware (>= 15.0)"


def read_ar(raw):
    assert len(raw) <= MAX_INPUT, "oversized original archive"
    assert raw[:8] == b"!<arch>\n", "not a Debian ar archive"
    cursor, members = 8, []
    while cursor < len(raw):
        assert len(members) < 3, "unexpected ar member count"
        header = raw[cursor:cursor + 60]
        assert len(header) == 60 and header[58:] == b"`\n", "invalid ar header"
        name = header[:16].decode("ascii").strip().removesuffix("/")
        field = header[48:58].decode("ascii").strip()
        assert field.isdecimal(), "invalid ar member size"
        size = int(field)
        cursor += 60
        assert size <= MAX_INPUT and cursor + size <= len(raw), "ar member outside archive"
        assert name not in {item[0] for item in members}, "duplicate ar member"
        members.append((name, raw[cursor:cursor + size]))
        cursor += size
        if size % 2:
            assert raw[cursor:cursor + 1] == b"\n", "invalid ar padding"
            cursor += 1
    assert cursor == len(raw) and len(members) == 3, "invalid Debian archive inventory"
    assert members[0] == ("debian-binary", b"2.0\n"), "unsupported Debian format"
    assert re.fullmatch(r"control\.tar(?:\.(?:gz|bz2|xz|lzma))?", members[1][0]), "missing control archive"
    assert re.fullmatch(r"data\.tar(?:\.(?:gz|bz2|xz|lzma))?", members[2][0]), "missing data archive"
    return members


def decompress_archive(name, raw, max_output=MAX_EXPANDED, memory_limit=LZMA_MEMORY):
    assert len(raw) <= MAX_INPUT, "oversized compressed archive"
    try:
        if name.endswith((".xz", ".lzma")):
            fmt = lzma.FORMAT_XZ if name.endswith(".xz") else lzma.FORMAT_ALONE
            decoder = lzma.LZMADecompressor(format=fmt, memlimit=memory_limit)
            expanded = decoder.decompress(raw, max_length=max_output + 1)
            assert len(expanded) <= max_output, "expanded archive exceeds limit"
            assert decoder.eof and not decoder.unused_data, "truncated or trailing compressed archive"
        elif name.endswith((".gz", ".bz2")):
            stream = gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") if name.endswith(".gz") else bz2.BZ2File(io.BytesIO(raw), mode="rb")
            with stream:
                expanded = stream.read(max_output + 1)
        else:
            expanded = raw
    except (lzma.LZMAError, OSError, EOFError) as error:
        raise AssertionError("archive decompression/memory failure: " + str(error)) from error
    assert len(expanded) <= max_output, "expanded archive exceeds limit"
    return expanded


def tar_inventory(raw):
    assert len(raw) <= MAX_EXPANDED, "oversized expanded tar"
    files, inventory, seen, total = {}, [], set(), 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for member in archive:
            assert len(inventory) < MAX_MEMBERS, "excessive tar member count"
            path = PurePosixPath(member.name)
            assert not path.is_absolute() and ".." not in path.parts, "unsafe archive path"
            assert not any(character in member.name for character in ("\\", "\0", "\n", "\r")), "ambiguous archive path"
            assert len(member.name) <= 1024, "oversized archive path"
            name = str(path)
            assert name not in seen, ("duplicate archive member", name)
            seen.add(name)
            assert member.isdir() or member.isfile(), ("link/special archive member", name)
            assert not member.mode & 0o6000, ("setid archive member", name)
            assert 0 <= member.size <= MAX_EXPANDED, "advertised member size exceeds limit"
            total += member.size
            assert total <= MAX_EXPANDED, "advertised expanded total exceeds limit"
            inventory.append({"path": name, "type": "directory" if member.isdir() else "file",
                              "mode": oct(member.mode), "uid": member.uid, "gid": member.gid,
                              "uname": member.uname, "gname": member.gname, "size": member.size})
            if member.isfile():
                assert name != ".", "empty archive filename"
                stream = archive.extractfile(member)
                assert stream is not None
                value = stream.read(member.size + 1)
                assert len(value) == member.size, "truncated tar member"
                files[name] = value
    return files, sorted(inventory, key=lambda row: row["path"])


def parse_control(raw):
    fields, lower, previous = {}, set(), None
    for line in raw.decode("utf-8").splitlines():
        if not line:
            continue
        if line.startswith((" ", "\t")):
            assert previous is not None, "orphan control continuation"
            fields[previous] += "\n" + line
            continue
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9-]*):[ \t]*(.*)", line)
        assert match is not None, "malformed control field"
        key, value = match.groups()
        assert key.lower() not in lower, ("duplicate control field", key)
        lower.add(key.lower()); fields[key] = value; previous = key
    return fields


def load_plist(raw):
    try:
        return plistlib.loads(raw)
    except (ValueError, TypeError, OverflowError, ExpatError) as error:
        raise AssertionError("invalid packaged plist: " + str(error)) from error


def strings_table(raw):
    if raw.startswith((b"bplist", b"<?xml", b"<plist")):
        values = load_plist(raw)
        assert isinstance(values, dict), "invalid localized strings plist"
        return values
    value = raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
    skip = re.compile(r"\s+|/\*.*?\*/|//[^\n]*(?:\n|$)", re.S)
    pair = re.compile(r'("(?:[^"\\]|\\.)*")\s*=\s*("(?:[^"\\]|\\.)*")\s*;', re.S)
    cursor, values = 0, {}
    while cursor < len(value):
        ignored = skip.match(value, cursor)
        if ignored:
            cursor = ignored.end(); continue
        match = pair.match(value, cursor)
        assert match is not None, "malformed localized strings"
        key, translated = (json.loads(item) for item in match.groups())
        assert key not in values, "duplicate localization key"
        assert translated, "empty localized value"
        values[key] = translated; cursor = match.end()
    assert values, "empty localization table"
    return values


def verify_resources(files):
    required = {TWEAK, FILTER, BUNDLE + "NoticeXPrefs", BUNDLE + "Info.plist", BUNDLE + "Root.plist", LOADER}
    assert required <= files.keys(), ("missing required payload", sorted(required - files.keys()))
    locales = {}
    allowed = set(required)
    for locale in ("en", "zh-Hans"):
        paths = sorted(name for name in files if re.fullmatch(re.escape(BUNDLE + locale + ".lproj/") + r"[^/]+\.strings", name))
        assert paths, ("missing Settings localization", locale)
        values = {}
        for path in paths:
            parsed = strings_table(files[path])
            assert not values.keys() & parsed.keys(), "duplicate localization across tables"
            values.update(parsed)
        allowed.update(paths); locales[locale] = values
    assert set(files) == allowed, ("unexpected payload / test fixtures / rootless paths", sorted(set(files) - allowed))
    assert load_plist(files[FILTER]) == {"Filter": {"Bundles": ["com.apple.springboard"]}}, "unsafe injection filter"
    info = load_plist(files[BUNDLE + "Info.plist"])
    assert isinstance(info, dict), "invalid Preferences bundle Info.plist"
    assert info.get("CFBundleExecutable") == "NoticeXPrefs", "wrong Preferences executable"
    assert info.get("NSPrincipalClass") == "NXSettingsController", "wrong Preferences entry class"
    assert info.get("CFBundleShortVersionString") == IDENTITY["Version"].split("-", 1)[0] and info.get("CFBundleVersion") == "1", "wrong Preferences bundle version"
    assert info.get("MinimumOSVersion") == "15.0", "wrong Preferences bundle deployment"
    assert info.get("CFBundleIdentifier") == "com.tsangbaby.noticex.preferences", "wrong bundle identity"
    rows = load_plist(files[BUNDLE + "Root.plist"])
    assert isinstance(rows, dict) and isinstance(rows.get("items"), list), "invalid Settings specifiers"
    rows = rows["items"]
    assert all(isinstance(row, dict) for row in rows), "invalid Settings row"
    switches = [row for row in rows if row.get("cell") == "PSSwitchCell"]
    assert len(switches) == 1, "Settings must expose exactly one switch"
    switch = switches[0]
    assert switch.get("key") == "enabled" and switch.get("default") is False, "unsafe enabled default"
    assert switch.get("defaults") == "com.tsangbaby.noticex", "wrong preferences domain"
    # Custom Swift accessors own the transactional save/notify path. Do not
    # require an unrelated plist PostNotification key when that path is wired.
    assert (switch.get("get"), switch.get("set")) == ("readPreferenceValue:", "setPreferenceValue:specifier:") or (
        isinstance(switch.get("PostNotification"), str) and bool(switch["PostNotification"])), "missing Settings reload/accessor wiring"
    assert all(row.get("cell") in ("PSGroupCell", "PSSwitchCell") for row in rows), "undeclared Settings option"
    labels = {row[key] for row in rows for key in ("label", "footerText") if row.get(key)}
    for locale, values in locales.items():
        assert labels <= values.keys(), ("unlocalized Settings label", locale, sorted(labels - values.keys()))
    loader = load_plist(files[LOADER])
    assert isinstance(loader, dict), "invalid PreferenceLoader plist"
    entry = loader.get("entry", {})
    assert isinstance(entry, dict), "invalid PreferenceLoader entry"
    assert entry.get("bundle") == "NoticeXPrefs" and entry.get("detail") == "NXSettingsController", "wrong PreferenceLoader entry"
    assert entry.get("isController") is True, "missing PreferenceLoader controller registration"
    assert entry.get("cell") == "PSLinkCell" and entry.get("label") == "Notice-X", "wrong Settings branding"
    return {"bundle_info": info, "switch": switch, "localizations": locales, "loader": loader}


def verify_dependencies(slices, module):
    for row in slices:
        loads = row["load_dylibs"]
        for value in loads + row["rpaths"] + row["install_names"]:
            assert "/var/jb" not in value and not value.startswith("var/jb"), "rootless load path in RootHide package"
            assert not any(word in value.lower() for word in ("orion", "glint", "cephei")), "undeclared runtime dependency"
        assert any(Path(value).name == "libswiftCore.dylib" for value in loads), "missing Swift runtime dependency"
        for value in loads:
            system = value.startswith(("/usr/lib/", "/System/Library/Frameworks/", "/System/Library/PrivateFrameworks/"))
            swift = value.startswith("@rpath/libswift") and value.endswith(".dylib")
            substrate = Path(value).name == "libsubstrate.dylib"
            assert system or swift or substrate, ("undeclared runtime dependency", value)
        if module == "NoticeX":
            assert any(Path(value).name == "libsubstrate.dylib" for value in loads), "missing substrate linkage"
            assert row["install_names"] == ["@loader_path/.jbroot/Library/MobileSubstrate/DynamicLibraries/NoticeX.dylib"], "wrong RootHide install name"
        else:
            assert any(value.endswith("/Preferences.framework/Preferences") for value in loads), "missing Preferences framework linkage"


def verify_package(package):
    if not __debug__:
        raise RuntimeError("Run without -O: assertions are required")
    package = Path(package)
    assert package.is_file() and not package.is_symlink(), "original package must be a regular file"
    assert package.stat().st_size <= MAX_INPUT, "oversized original archive"
    raw = package.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    ar = read_ar(raw)
    control_files, control_inventory = tar_inventory(decompress_archive(*ar[1]))
    assert "control" in control_files and set(control_files) <= {"control", "md5sums"}, "undeclared control file / maintainer script"
    fields = parse_control(control_files["control"])
    for key, expected in IDENTITY.items():
        assert fields.get(key) == expected, ("package metadata mismatch", key, fields.get(key), expected)
    assert fields.get("Depends") == DEPENDENCIES, "package metadata dependency mismatch"
    # Independent real Debian parser must accept these same original bytes.
    parsed = subprocess.run(["dpkg-deb", "-f", str(package)], text=True, capture_output=True, timeout=30)
    assert parsed.returncode == 0, ("dpkg-deb rejected original metadata", parsed.stderr)
    assert parse_control(parsed.stdout.encode()) == fields, "Debian parser metadata disagreement"
    files, inventory = tar_inventory(decompress_archive(*ar[2]))
    assert not any(name == "var/jb" or name.startswith("var/jb/") for name in files), "rootless payload in RootHide package"
    resources = verify_resources(files)
    allowed_dirs = {"."}
    for name in files:
        allowed_dirs.update(str(parent) for parent in PurePosixPath(name).parents)
    assert all(row["type"] != "directory" or row["path"] in allowed_dirs for row in inventory), "unexpected payload directory / rootless paths"
    magics = (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf",
              b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce", b"\xbe\xba\xfe\xca", b"\xbf\xba\xfe\xca")
    machos = sorted(name for name, value in files.items() if value.startswith(magics))
    assert machos == sorted([TWEAK, BUNDLE + "NoticeXPrefs"]), ("unexpected Mach-O inventory", machos)
    binaries = []
    with tempfile.TemporaryDirectory(prefix="noticex-verify-", dir=os.environ.get("RUNNER_TEMP") or os.environ.get("TMPDIR")) as folder:
        for index, name in enumerate(machos):
            path = Path(folder) / str(index)
            path.write_bytes(files[name])
            module = "NoticeX" if name == TWEAK else "NoticeXPrefs"
            slices = verify_macho(path, module=module)
            verify_dependencies(slices, module)
            binaries.append({"path": name, "sha256": hashlib.sha256(files[name]).hexdigest(), "slices": slices})
    assert package.read_bytes() == raw, "original package changed during verification"
    return {"package": package.name, "bytes": len(raw), "sha256": sha, "control": fields,
            "control_inventory": control_inventory, "payload_inventory": inventory,
            "file_count": len(files), "payload_files": sorted(files), "binaries": binaries,
            "resources": resources, "scheme": "roothide", "device_tested": False,
            "signature_evidence": "structure_and_code_page_hashes_not_signer_trust",
            "swift_evidence": "defined_module_instruction_symbols_not_runtime_execution"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        result = verify_package(args.package)
        text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.report:
            assert args.report.resolve() != args.package.resolve(), "report cannot overwrite original package"
            args.report.write_text(text)
        print(text, end="")
    except (AssertionError, RuntimeError, OSError, ValueError, TypeError, struct.error, tarfile.TarError, ExpatError,
            subprocess.SubprocessError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
