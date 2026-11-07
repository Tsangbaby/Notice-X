#!/usr/bin/env python3
"""Read-only ARM64 Mach-O signature bounds and code-page hash verifier.

Invoke with extracted binaries, not a compressed .deb or Actions ZIP.
Defaults to the exact architecture set arm64+arm64e; repeat --arch to override.
Supports big-endian FAT32/FAT64 containers and 64-bit ARM Mach-O slices.
Nonlinear CodeDirectory scatter layouts are rejected as unsupported.
Evidence is signature structure and code-page integrity, not signer trust,
entitlement validation, jailbreak runtime compatibility, or device acceptance.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


def bounded(buf, off, size):
    assert isinstance(off, int) and off >= 0 and size >= 0 and off + size <= len(buf), (
        "out-of-bounds region", off, size, len(buf)
    )
    return buf[off:off + size]


def u32be(buf, off):
    return struct.unpack(">I", bounded(buf, off, 4))[0]


def slice_metadata(blob, endian, ncmds, sizeofcmds, module):
    """Inspect binary ABI structures, not guessed compiler stdout/literals.

    N_SECT symbols in an instruction section are emitted code evidence. Imported
    Swift runtime symbols and strings in resource/data blobs cannot satisfy it.
    """
    cursor, builds, symtabs, sections, install_names = 32, [], [], [], []
    for _ in range(ncmds):
        cmd, size = struct.unpack(endian + "II", bounded(blob, cursor, 8))
        command = bounded(blob, cursor, size)
        if cmd == 0x32:
            assert size >= 24, "short LC_BUILD_VERSION"
            platform, minimum, sdk, count = struct.unpack(endian + "IIII", command[8:24])
            assert size == 24 + 8 * count, "invalid LC_BUILD_VERSION tools"
            builds.append((platform, minimum))
        elif cmd == 0x25:
            assert size == 16, "short LC_VERSION_MIN_IPHONEOS"
            builds.append((2, struct.unpack(endian + "I", command[8:12])[0]))
        elif cmd == 2:
            assert size == 24, "invalid LC_SYMTAB"
            symtabs.append(struct.unpack(endian + "IIII", command[8:24]))
        elif cmd == 0x19:
            assert size >= 72, "short LC_SEGMENT_64"
            count = struct.unpack(endian + "I", command[64:68])[0]
            assert size == 72 + 80 * count, "invalid section table"
            for index in range(count):
                section = command[72 + index * 80:152 + index * 80]
                address, length, offset = struct.unpack(endian + "QQI", section[32:52])
                flags = struct.unpack(endian + "I", section[64:68])[0]
                if flags & 0x80000400:
                    bounded(blob, offset, length)
                sections.append((address, length, bool(flags & 0x80000400)))
        elif cmd == 0xD:
            assert size >= 24, "short LC_ID_DYLIB"
            nameoff = struct.unpack(endian + "I", command[8:12])[0]
            assert 24 <= nameoff < size, "invalid install name offset"
            value = command[nameoff:].split(b"\0", 1)
            assert len(value) == 2, "unterminated install name"
            install_names.append(value[0].decode())
        cursor += size
    assert cursor == 32 + sizeofcmds
    assert len(builds) == 1 and builds[0][0] == 2, "not an iPhoneOS device platform"
    minimum = builds[0][1]
    version = [minimum >> 16, (minimum >> 8) & 255, minimum & 255]
    assert version == [15, 0, 0], ("deployment must be iOS 15.0", version)
    assert len(symtabs) == 1, "missing/duplicate symbol table for Swift evidence"
    symoff, count, stroff, strsize = symtabs[0]
    assert count <= 1000000, "excessive symbol count"
    table = bounded(blob, symoff, count * 16)
    strings = bounded(blob, stroff, strsize)
    defined, code = [], []
    for index in range(count):
        strx, typ, sect, desc, value = struct.unpack(endian + "IBBHQ", table[index * 16:(index + 1) * 16])
        assert strx < len(strings), "symbol string offset out of bounds"
        terminator = strings.find(b"\0", strx)
        assert terminator >= 0, "unterminated symbol"
        if typ & 0xE0 or typ & 0xE != 0xE:  # exclude debug and undefined/imported entries
            continue
        assert 1 <= sect <= len(sections), "symbol section out of bounds"
        decoded = strings[strx:terminator].decode("utf-8")
        defined.append(decoded)
        address, length, instructions = sections[sect - 1]
        if instructions and address <= value < address + length:
            code.append(decoded)
    swift = []
    if module is not None:
        prefix = "_$s" + str(len(module.encode())) + module
        swift = sorted(set(name for name in code if name.startswith(prefix)))
        assert swift, ("no defined Swift instruction symbols for module", module)
        if module == "NoticeXPrefs":
            assert "_OBJC_CLASS_$_NXSettingsController" in defined, "missing Settings entry class symbol"
    return {"platform": "iPhoneOS", "minimum_os": version,
            "install_names": install_names, "swift_module": module,
            "swift_defined_symbols": swift, "defined_symbol_count": len(defined)}


def verify_macho(path, expected_archs=("arm64", "arm64e"), module=None):
    if not __debug__:
        raise RuntimeError("Run without -O: assertions are required")
    data = path.read_bytes()
    magic = u32be(data, 0)
    if magic in (0xcafebabe, 0xcafebabf):
        count = u32be(data, 4)
        assert 1 <= count <= 4, "unsupported FAT slice count"
        width = 20 if magic == 0xcafebabe else 32
        bounded(data, 8, count * width)
        slices = []
        for index in range(count):
            fmt = ">iiIII" if width == 20 else ">iiQQII"
            entry = struct.unpack(fmt, bounded(data, 8 + index * width, width))
            cpu, subtype, offset, size = entry[:4]
            assert offset >= 8 + count * width, "slice overlaps FAT header"
            bounded(data, offset, size)
            slices.append((offset, size, cpu, subtype))
        ranges = sorted((off, off + size) for off, size, _, _ in slices)
        assert all(ranges[i][1] <= ranges[i + 1][0] for i in range(len(ranges) - 1)), (
            "overlapping FAT slices"
        )
    else:
        slices = [(0, len(data), None, None)]

    results = []
    for offset, size, fatcpu, fatsub in slices:
        blob = bounded(data, offset, size)
        if blob[:4] == b"\xcf\xfa\xed\xfe":
            endian = "<"
        elif blob[:4] == b"\xfe\xed\xfa\xcf":
            endian = ">"
        else:
            raise AssertionError("not a supported 64-bit Mach-O slice")
        header = struct.unpack(endian + "IiiIIIII", bounded(blob, 0, 32))
        _, cpu, subtype, filetype, ncmds, sizeofcmds, flags, reserved = header
        assert cpu == 0x0100000c and (subtype & 0x00ffffff) in (0, 2), (
            "unsupported CPU architecture", cpu, subtype
        )
        if fatcpu is not None:
            assert cpu == fatcpu and subtype == fatsub, "FAT/slice CPU mismatch"
        arch = "arm64e" if subtype & 0x00ffffff == 2 else "arm64"
        assert 0 < ncmds < 10000 and 32 + sizeofcmds <= len(blob), (
            "invalid load-command region"
        )
        cursor = 32
        signature_commands = []
        loads = []
        rpaths = []
        for _ in range(ncmds):
            cmd, cmdsize = struct.unpack(endian + "II", bounded(blob, cursor, 8))
            assert cmdsize >= 8 and cursor + cmdsize <= 32 + sizeofcmds, (
                "load command outside declared region"
            )
            command = bounded(blob, cursor, cmdsize)
            if cmd == 0x1d:
                assert cmdsize == 16, "invalid LC_CODE_SIGNATURE size"
                sigoff, sigsize = struct.unpack(endian + "II", command[8:16])
                bounded(blob, sigoff, sigsize)
                assert sigoff >= 32 + sizeofcmds, "signature overlaps load commands"
                signature_commands.append((sigoff, sigsize))
            if cmd in (0xc, 0x80000018, 0x8000001f, 0x80000023):
                assert cmdsize >= 24, "invalid dylib load command"
                nameoff = struct.unpack(endian + "I", command[8:12])[0]
                assert 24 <= nameoff < cmdsize, "invalid dylib-name offset"
                name = command[nameoff:].split(b"\0", 1)
                assert len(name) == 2, "unterminated dylib name"
                loads.append(name[0].decode())
            if cmd == 0x8000001c:
                assert cmdsize >= 12, "invalid LC_RPATH"
                nameoff = struct.unpack(endian + "I", command[8:12])[0]
                assert 12 <= nameoff < cmdsize, "invalid rpath offset"
                name = command[nameoff:].split(b"\0", 1)
                assert len(name) == 2, "unterminated rpath"
                rpaths.append(name[0].decode())
            cursor += cmdsize
        assert cursor == 32 + sizeofcmds and len(signature_commands) == 1, (
            "load-command length or signature-command count mismatch"
        )

        sigoff, sigsize = signature_commands[0]
        signature = bounded(blob, sigoff, sigsize)
        assert u32be(signature, 0) == 0xfade0cc0, "not an embedded-signature SuperBlob"
        superlen, nblobs = u32be(signature, 4), u32be(signature, 8)
        assert 12 <= superlen <= len(signature) and 0 < nblobs <= 50, (
            "invalid SuperBlob length/count"
        )
        bounded(signature, 12, nblobs * 8)
        assert 12 + nblobs * 8 <= superlen, "SuperBlob index exceeds length"
        codedirs = []
        blobranges = []
        for index in range(nblobs):
            typ, suboff = struct.unpack(">II", bounded(signature, 12 + 8 * index, 8))
            assert suboff >= 12 + 8 * nblobs, "signature subblob overlaps index"
            submagic, sublen = struct.unpack(">II", bounded(signature, suboff, 8))
            assert sublen >= 8 and suboff + sublen <= superlen, (
                "signature subblob exceeds SuperBlob"
            )
            subblob = bounded(signature, suboff, sublen)
            blobranges.append((suboff, suboff + sublen))
            if submagic != 0xfade0c02:
                continue
            assert len(subblob) >= 44, "short CodeDirectory"
            fields = struct.unpack(">9I4BI", subblob[:44])
            (_, length, version, cdflags, hashoff, identoff, nspecial,
             nslots, codelimit, hashsize, hashtype, platform, pageexp, spare) = fields
            assert length == sublen and 44 <= identoff < sublen, "invalid identifier offset"
            assert b"\0" in subblob[identoff:], "unterminated CodeDirectory identifier"
            assert hashsize in (20, 32, 48) and hashtype in (1, 2, 3, 4), (
                "unsupported CodeDirectory hash"
            )
            assert pageexp <= 30, "unsupported code-page exponent"
            if version >= 0x20100:
                assert u32be(subblob, 44) == 0, "unsupported nonlinear scatter directory"
            if version >= 0x20300:
                code64 = struct.unpack(">Q", bounded(subblob, 56, 8))[0]
                if code64:
                    codelimit = code64
            assert codelimit == sigoff and codelimit > 0, "signed code range must cover all pre-signature bytes"
            assert hashoff - nspecial * hashsize >= 44, "special hashes outside directory"
            assert hashoff + nslots * hashsize <= sublen, "code hashes outside directory"
            pagesize = 1 << pageexp if pageexp else codelimit
            assert nslots == (codelimit + pagesize - 1) // pagesize, (
                "CodeDirectory page-slot count mismatch"
            )
            hash_fn = {
                1: hashlib.sha1, 2: hashlib.sha256,
                3: hashlib.sha256, 4: hashlib.sha384,
            }[hashtype]
            assert hashsize == {1: 20, 2: 32, 3: 20, 4: 48}[hashtype], (
                "CodeDirectory hash-size mismatch"
            )
            for slot in range(nslots):
                chunk = blob[slot * pagesize:min((slot + 1) * pagesize, codelimit)]
                computed = hash_fn(chunk).digest()[:hashsize]
                stored = subblob[hashoff + slot * hashsize:hashoff + (slot + 1) * hashsize]
                assert stored == computed, (path.name, arch, "code-page hash mismatch", slot)
            codedirs.append({
                "hash_type": hashtype,
                "code_slots": nslots,
                "all_code_page_hashes_verified": True,
            })
        assert codedirs, "no CodeDirectory"
        blobranges.sort()
        assert all(blobranges[i][1] <= blobranges[i + 1][0]
                   for i in range(len(blobranges) - 1)), "overlapping signature subblobs"
        metadata = slice_metadata(blob, endian, ncmds, sizeofcmds, module) if module else {}
        if module:
            assert filetype == (6 if module == "NoticeX" else 8), "wrong Mach-O target file type"
        results.append({
            **metadata,
            "architecture": arch,
            "code_signature_bounded": True,
            "code_directories": codedirs,
            "load_dylibs": loads,
            "rpaths": rpaths,
        })
    expected = set(expected_archs)
    assert {sliceinfo["architecture"] for sliceinfo in results} == expected, (
        "architecture-set mismatch", sorted(expected)
    )
    assert len(results) == len(expected), "duplicate architecture slices"
    return results


def main():
    if not __debug__:
        print("ERROR: run without -O; assertion checks are required", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", action="append", choices=("arm64", "arm64e"),
                        help="required architecture; repeat for a multi-slice binary")
    parser.add_argument("binaries", nargs="+", type=Path)
    args = parser.parse_args()
    expected = args.arch or ["arm64", "arm64e"]
    reports = []
    try:
        for path in args.binaries:
            reports.append({"path": str(path), "slices": verify_macho(path, expected)})
    except (AssertionError, OSError, ValueError, struct.error) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps({
        "evidence": "signature_structure_and_code_page_hashes_only",
        "expected_architectures": sorted(set(expected)),
        "binary_count": len(reports),
        "binaries": reports,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
