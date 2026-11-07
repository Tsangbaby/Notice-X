"""Isolated build/release contracts; no parent-owned source files required.

Synthetic archives below are adversarial parser fixtures, never product evidence.
"""
import importlib.util
import json
import pathlib
import plistlib
import re
import subprocess
import hashlib
import io
import lzma
import struct
import sys
import tarfile
import tempfile
from unittest.mock import patch
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def text(path):
    target = ROOT / path
    return target.read_text() if target.is_file() else ""


def assignments(path):
    value = text(path).replace("\\\n", " ")
    return dict(re.findall(r"^([A-Za-z0-9_]+)\s*(?:\?|\+|:)?=\s*(.*)$", value, re.M))


class NXBuildMetadataContract(unittest.TestCase):
    def test_exact_swift_graph_and_roothide_identity(self):
        main, prefs = assignments("Makefile"), assignments("prefs/Makefile")
        self.assertEqual(main.get("TWEAK_NAME"), "NoticeX", "missing NoticeX build graph")
        self.assertEqual(main.get("THEOS_PACKAGE_SCHEME"), "roothide")
        self.assertEqual(main.get("TARGET"), "iphone:clang:18.5:15.0")
        self.assertEqual(main.get("ARCHS"), "arm64 arm64e")
        self.assertEqual(main.get("NoticeX_FILES", "").split(), [
            "Sources/Core/NoticePolicy.swift", "Sources/Support/NoticePreferences.swift",
            "Sources/Support/NoticeDiagnostics.swift", "Sources/Native/NoticeXDiagnostics.m",
            "Sources/Runtime/NoticeRuntime.swift", "Sources/UI/NoticeCardAnimator.swift",
            "Sources/UI/NoticeBannerCoordinator.swift", "Sources/Native/NoticeXBootstrap.m"])
        self.assertEqual(main.get("NoticeX_LIBRARIES"), "substrate")
        self.assertEqual(main.get("NoticeX_SWIFT_BRIDGING_HEADER"), "Sources/Native/NoticeXBridge.h")
        self.assertEqual(main.get("NoticeX_STRIP_FLAGS"), "-S")
        self.assertEqual(main.get("SUBPROJECTS"), "prefs")
        self.assertIn("aggregate.mk", text("Makefile"))
        self.assertEqual(prefs.get("BUNDLE_NAME"), "NoticeXPrefs")
        self.assertEqual(prefs.get("NoticeXPrefs_FILES", "").split(), [
            "NoticeXPreferences.swift", "../Sources/Core/NoticePolicy.swift",
            "../Sources/Support/NoticePreferences.swift"])
        self.assertEqual(prefs.get("NoticeXPrefs_PRIVATE_FRAMEWORKS"), "Preferences")
        self.assertEqual(prefs.get("NoticeXPrefs_RESOURCE_DIRS"), "Resources")
        self.assertEqual(prefs.get("NoticeXPrefs_SWIFT_BRIDGING_HEADER"), "NoticeXPreferencesBridge.h")
        self.assertEqual(prefs.get("NoticeXPrefs_STRIP_FLAGS"), "-S")
        self.assertEqual(prefs.get("TARGET"), main.get("TARGET"))
        self.assertEqual(prefs.get("ARCHS"), main.get("ARCHS"))
        control = dict(re.findall(r"^([\w-]+): (.*)$", text("control"), re.M))
        self.assertEqual(control.get("Package"), "com.tsangbaby.noticex")
        self.assertEqual(control.get("Name"), "Notice-X")
        self.assertEqual(control.get("Version"), "0.1.0-beta3")
        self.assertEqual(control.get("Architecture"), "iphoneos-arm64e")
        for key in ("Author", "Maintainer"):
            self.assertEqual(control.get(key), "Tsangbaby")
        self.assertEqual(control.get("Depends"), "mobilesubstrate, preferenceloader, firmware (>= 15.0)")
        self.assertNotIn("Installed-Size", control, "Theos appends this generated field")
        keys = re.findall(r"^([\w-]+):", text("control") + "Installed-Size: 1\n", re.M)
        self.assertEqual(len(keys), len(set(key.lower() for key in keys)))
        self.assertEqual(plistlib.loads((ROOT / "NoticeX.plist").read_bytes()),
                         {"Filter": {"Bundles": ["com.apple.springboard"]}})
        for word in ("Orion", "Logos", "SwiftUI", "dynamic_lookup"):
            self.assertNotIn(word, text("Makefile") + text("prefs/Makefile"))


class NXWorkflowContract(unittest.TestCase):
    def test_preferences_stub_is_in_the_scheme_specific_framework_search_root(self):
        workflow=json.loads(text('.github/workflows/roothide.yml'))
        job=workflow['jobs']['build']
        step=[s for s in job['steps'] if s['name']=='Stage hash-pinned Preferences link stub only']
        self.assertEqual(len(step),1)
        body=step[0]['run']
        expected='$THEOS/lib/iphone/'+job['env']['THEOS_PACKAGE_SCHEME']+'/Preferences.framework'
        targets=re.findall(r'(?m)^\s*target="([^"]+)"',body)
        self.assertEqual(targets,[expected+'/Preferences.tbd'],
                         'stub must live in the scheme-specific Theos framework search root')
        self.assertIn('mkdir -p "'+expected+'"',body)

    def test_one_pinned_cloud_lane_preserves_failure_and_original(self):
        raw = text(".github/workflows/roothide.yml")
        self.assertTrue(raw, "missing pinned RootHide workflow")
        workflow = json.loads(raw)  # JSON is also YAML; no YAML parser dependency.
        self.assertEqual(workflow["on"], {"push": {"branches": ["main", "diag/banner-entry-1541", "fix/banner-session-admission-1541", "fix/whole-shell-reveal-beta3"]}})
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(set(workflow["jobs"]), {"build"})
        job = workflow["jobs"]["build"]
        self.assertEqual(job["runs-on"], "macos-15")
        self.assertEqual(job["env"]["DEVELOPER_DIR"], "/Applications/Xcode_16.4.app/Contents/Developer")
        self.assertEqual(job["env"]["THEOS_COMMIT"], "3ac89c984ec652fd16bcd91b33ae16de45ce76fa")
        steps = job["steps"]
        uses = [step for step in steps if "uses" in step]
        self.assertEqual(uses[0]["uses"], "actions/checkout@11d5960a326750d5838078e36cf38b85af677262")
        self.assertFalse(uses[0]["with"]["persist-credentials"])
        self.assertEqual(uses[-1]["uses"], "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02")
        self.assertEqual(uses[-1]["if"], "always()")
        self.assertEqual(uses[-1]["with"]["if-no-files-found"], "error")
        bodies = "\n".join(step.get("run", "") for step in steps)
        for step in steps:
            if "run" in step:
                self.assertTrue(step["run"].startswith("set -euo pipefail\n"))
                checked = subprocess.run(["bash", "-n"], input=step["run"], text=True, capture_output=True)
                self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertNotIn("continue-on-error", step)
        for required in ("brew install make dpkg ldid", "--init --recursive", "0222fd5413cf4b9af096f37b4621afa2688572f7",
                         "9daceaff6cf94346594a12f9ef9c2ea23de15475b516f9e33c20871a018c098b",
                         "test_*.py", "tests/run_swift_tests.py --out ci-artifacts/swift-tests",
                         "make -k -j2 package", "INSTALL=0", "SYSROOT=", "SDKVERSION=18.5",
                         "tee ci-artifacts/theos-build.log", "tools/verify_package.py", "ci_evidence.py retain",
                         "ci_evidence.py manifest", "SDKROOT=", "--show-sdk-version"):
            self.assertIn(required, bodies)
        self.assertLess(bodies.index("brew install"), bodies.index("unittest discover"))
        self.assertLess(bodies.index("ci_evidence.py retain"), bodies.index("tools/verify_package.py"))
        self.assertNotIn("TARGET_CODESIGN=", bodies)
        self.assertNotIn("simctl", bodies)
        self.assertNotIn("0.1.0-beta1", bodies, "derive version from control")


def nx_tool(case, name):
    path = ROOT / "tools" / (name + ".py")
    case.assertTrue(path.is_file(), "missing independent " + name + " verifier")
    with patch.object(sys, "path", [str(path.parent)] + sys.path):
        spec = importlib.util.spec_from_file_location("_nx_contract_" + name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return module


def nx_thin(subtype=0, module="NoticeX", platform=2, minimum=0xF0000, swift=True, filetype=6):
    """Tiny signed *synthetic* parser fixture, NOT an Apple compilation."""
    def dylib(cmd, name):
        value = name.encode() + b"\0"
        size = (24 + len(value) + 7) // 8 * 8
        return struct.pack("<6I", cmd, size, 24, 0, 0, 0) + value + bytes(size - 24 - len(value))
    codeoff, sigoff = 768, 2048
    symbol = ("_$s" + str(len(module)) + module + "5probeSiyF") if swift else "_nativeOnly"
    names = b"\0" + symbol.encode() + b"\0_OBJC_CLASS_$_NXSettingsController\0"
    symoff, stroff = 1024, 1056
    symbols = struct.pack("<IBBHQ", 1, 0xF, 1, 0, 0x100000000 + codeoff)
    symbols += struct.pack("<IBBHQ", 2 + len(symbol), 0xF, 1, 0, 0x100000000 + codeoff + 4)
    section = struct.pack("<16s16sQQIIIIIIII", b"__text", b"__TEXT", 0x100000000 + codeoff,
                          16, codeoff, 2, 0, 0, 0x80000400, 0, 0, 0)
    segment = struct.pack("<II16sQQQQiiII", 0x19, 152, b"__TEXT", 0x100000000,
                          sigoff, 0, sigoff, 7, 5, 1, 0) + section
    ident = b"synthetic.noticex\0"
    cdsize = 44 + len(ident) + 32
    sigsize = 20 + cdsize
    commands = [segment, struct.pack("<6I", 0x32, 24, platform, minimum, 0x120500, 0),
                struct.pack("<6I", 2, 24, symoff, 2, stroff, len(names)),
                struct.pack("<4I", 0x1D, 16, sigoff, sigsize),
                dylib(0xC, "/usr/lib/libobjc.A.dylib"),
                dylib(0xC, "/usr/lib/swift/libswiftCore.dylib")]
    if module == "NoticeX":
        commands += [dylib(0xC, "@rpath/libsubstrate.dylib"),
                     dylib(0xD, "@loader_path/.jbroot/Library/MobileSubstrate/DynamicLibraries/NoticeX.dylib")]
    else:
        commands += [dylib(0xC, "/System/Library/PrivateFrameworks/Preferences.framework/Preferences")]
    header = struct.pack("<IiiIIIII", 0xFEEDFACF, 0x100000C, subtype,
                         filetype, len(commands), sum(map(len, commands)), 0, 0)
    body = bytearray(sigoff)
    body[:len(header)] = header
    body[32:32 + sum(map(len, commands))] = b"".join(commands)
    body[codeoff:codeoff + 16] = b"SYNTHETIC-FIXTUR"
    body[symoff:symoff + len(symbols)] = symbols
    body[stroff:stroff + len(names)] = names
    cd = struct.pack(">9I4BI", 0xFADE0C02, cdsize, 0x20001, 2, 44 + len(ident), 44,
                     0, 1, sigoff, 32, 2, 0, 12, 0) + ident + hashlib.sha256(body).digest()
    return bytes(body) + struct.pack(">5I", 0xFADE0CC0, sigsize, 1, 0, 20) + cd


def nx_fat(module="NoticeX", **kwargs):
    a, b = nx_thin(0, module, **kwargs), nx_thin(2, module, **kwargs)
    header = struct.pack(">II", 0xCAFEBABE, 2)
    header += struct.pack(">iiIII", 0x100000C, 0, 4096, len(a), 12)
    header += struct.pack(">iiIII", 0x100000C, 2, 8192, len(b), 12)
    return header + bytes(4096 - len(header)) + a + bytes(4096 - len(a)) + b


NX_TWEAK = "Library/MobileSubstrate/DynamicLibraries/NoticeX.dylib"
NX_BUNDLE = "Library/PreferenceBundles/NoticeXPrefs.bundle/"


def nx_payload():
    p = lambda value: plistlib.dumps(value, fmt=plistlib.FMT_BINARY)
    return {NX_TWEAK: nx_fat(),
            "Library/MobileSubstrate/DynamicLibraries/NoticeX.plist": p({"Filter": {"Bundles": ["com.apple.springboard"]}}),
            NX_BUNDLE + "NoticeXPrefs": nx_fat("NoticeXPrefs"),
            NX_BUNDLE + "Info.plist": p({"CFBundleExecutable": "NoticeXPrefs", "CFBundleIdentifier": "com.tsangbaby.noticex.preferences",
                                         "NSPrincipalClass": "NXSettingsController", "CFBundleShortVersionString": "0.1.0",
                                         "CFBundleVersion": "1", "MinimumOSVersion": "15.0"}),
            NX_BUNDLE + "Root.plist": p({"items": [{"cell": "PSGroupCell", "label": "NOTICE_X"},
                {"cell": "PSSwitchCell", "label": "ENABLED", "key": "enabled", "default": False,
                 "defaults": "com.tsangbaby.noticex", "PostNotification": "com.tsangbaby.noticex/preferences.changed"}]}),
            NX_BUNDLE + "en.lproj/Root.strings": b'"NOTICE_X" = "Notice-X";\n"ENABLED" = "Enabled";\n',
            NX_BUNDLE + "zh-Hans.lproj/Root.strings": '"NOTICE_X" = "Notice-X";\n"ENABLED" = "启用";\n'.encode(),
            "Library/PreferenceLoader/Preferences/NoticeX.plist": p({"entry": {"bundle": "NoticeXPrefs", "cell": "PSLinkCell",
                "label": "Notice-X", "detail": "NXSettingsController", "isController": True}})}


def nx_tar(files, extra=None):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name, value in files.items():
            entry = tarfile.TarInfo("./" + name)
            entry.size = len(value)
            entry.mode = 0o755 if name == NX_TWEAK or name.endswith("/NoticeXPrefs") else 0o644
            tar.addfile(entry, io.BytesIO(value))
        if extra is not None:
            tar.addfile(extra, io.BytesIO(b"x" * extra.size) if extra.isfile() else None)
    return out.getvalue()


def nx_deb(files=None, control=None, extra=None):
    metadata = (control if control is not None else text("control")).encode()
    members = [("debian-binary", b"2.0\n"), ("control.tar.gz", __import__("gzip").compress(nx_tar({"control": metadata}))),
               ("data.tar.xz", lzma.compress(nx_tar(nx_payload() if files is None else files, extra)))]
    result = bytearray(b"!<arch>\n")
    for name, value in members:
        result += (name + "/").ljust(16).encode() + b"0           0     0     100644  " + str(len(value)).ljust(10).encode() + b"`\n"
        result += value + (b"\n" if len(value) % 2 else b"")
    return bytes(result)


class NXOriginalDebContract(unittest.TestCase):
    def verify(self, raw):
        module = nx_tool(self, "verify_package")
        with tempfile.TemporaryDirectory(prefix="nx-parser-", dir=__import__("os").environ.get("TMPDIR")) as folder:
            path = pathlib.Path(folder) / "fixture.deb"
            path.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            result = module.verify_package(path)
            self.assertEqual(path.read_bytes(), raw, "verifier must not rewrite original package")
            self.assertEqual(result["sha256"], digest)
            return result

    def test_original_package_metadata_resources_and_every_signed_slice(self):
        report = self.verify(nx_deb())
        self.assertEqual(report["control"]["Package"], "com.tsangbaby.noticex")
        self.assertFalse(report["device_tested"])
        self.assertEqual(report["file_count"], len(nx_payload()))
        self.assertEqual(len(report["binaries"]), 2)
        for binary in report["binaries"]:
            self.assertEqual({row["architecture"] for row in binary["slices"]}, {"arm64", "arm64e"})
            for row in binary["slices"]:
                self.assertEqual(row["minimum_os"], [15, 0, 0])
                self.assertTrue(row["swift_defined_symbols"])
                self.assertTrue(all(cd["all_code_page_hashes_verified"] for cd in row["code_directories"]))

    def test_theos_preferences_is_dynamic_library_not_macho_bundle(self):
        # Pinned iPhoneOS bundle.mk links with -dynamiclib, even inside a .bundle directory.
        files=nx_payload()
        files[NX_BUNDLE+'NoticeXPrefs']=nx_fat('NoticeXPrefs',filetype=6)
        self.verify(nx_deb(files))
        for name,module in ((NX_TWEAK,'NoticeX'),(NX_BUNDLE+'NoticeXPrefs','NoticeXPrefs')):
            with self.subTest(target=module):
                invalid=dict(files)
                invalid[name]=nx_fat(module,filetype=8)
                with self.assertRaisesRegex(AssertionError,'file type'):
                    self.verify(nx_deb(invalid))

    def test_rejects_missing_or_disabled_preferenceloader_controller_registration(self):
        path='Library/PreferenceLoader/Preferences/NoticeX.plist'
        for value in (None,False):
            with self.subTest(isController=value):
                files=nx_payload()
                loader=plistlib.loads(files[path])
                if value is None:
                    loader['entry'].pop('isController')
                else:
                    loader['entry']['isController']=value
                files[path]=plistlib.dumps(loader,fmt=plistlib.FMT_BINARY)
                with self.assertRaisesRegex(AssertionError,'PreferenceLoader controller registration'):
                    self.verify(nx_deb(files))

    def test_rejects_stale_preferences_bundle_version(self):
        files = nx_payload()
        info = plistlib.loads(files[NX_BUNDLE + "Info.plist"])
        info["CFBundleShortVersionString"] = "9.9.9"
        files[NX_BUNDLE + "Info.plist"] = plistlib.dumps(info)
        with self.assertRaisesRegex(AssertionError, "bundle version"):
            self.verify(nx_deb(files))

    def test_custom_swift_preference_accessors_are_valid_without_postnotification(self):
        files = nx_payload()
        root = plistlib.loads(files[NX_BUNDLE + "Root.plist"])
        switch = root["items"][1]
        switch.pop("PostNotification")
        switch.update({"get": "readPreferenceValue:", "set": "setPreferenceValue:specifier:"})
        files[NX_BUNDLE + "Root.plist"] = plistlib.dumps(root)
        self.verify(nx_deb(files))

    def test_rejects_bad_code_page_even_when_signature_is_present(self):
        files = nx_payload()
        binary = bytearray(files[NX_TWEAK]); binary[4096 + 768] ^= 1
        files[NX_TWEAK] = bytes(binary)
        with self.assertRaisesRegex(AssertionError, "code-page hash mismatch"):
            self.verify(nx_deb(files))

    def test_rejects_simulator_or_wrong_minimum(self):
        for kwargs in ({"platform": 7}, {"minimum": 0x100000}, {"minimum": 0xE0000}):
            with self.subTest(kwargs=kwargs):
                files = nx_payload(); files[NX_TWEAK] = nx_fat(platform=kwargs.get("platform", 2), minimum=kwargs.get("minimum", 0xF0000))
                with self.assertRaisesRegex(AssertionError, "platform|deployment"):
                    self.verify(nx_deb(files))

    def test_rejects_absent_swift_symbols_in_each_slice(self):
        files = nx_payload(); files[NX_TWEAK] = nx_fat(swift=False)
        with self.assertRaisesRegex(AssertionError, "Swift"):
            self.verify(nx_deb(files))

    def test_rejects_duplicate_fields_and_wrong_identity(self):
        for control in (text("control") + "Package: com.tsangbaby.noticex\n",
                        text("control").replace("Tsangbaby", "Other"),
                        text("control").replace("iphoneos-arm64e", "iphoneos-arm64")):
            with self.subTest(control=control):
                with self.assertRaisesRegex(AssertionError, "duplicate|metadata"):
                    self.verify(nx_deb(control=control))

    def test_rejects_unsafe_filter_enabled_default_and_extra_fixture(self):
        base = nx_payload()
        variations = [dict(base, **{"var/jb/test.txt": b"bad"}), dict(base, **{"tests/host.swift": b"bad"})]
        unsafe = dict(base)
        unsafe["Library/MobileSubstrate/DynamicLibraries/NoticeX.plist"] = plistlib.dumps({"Filter": {"Bundles": ["com.apple.Preferences"]}})
        variations.append(unsafe)
        unsafe = dict(base)
        rows = plistlib.loads(unsafe[NX_BUNDLE + "Root.plist"])
        rows["items"][1]["default"] = True
        unsafe[NX_BUNDLE + "Root.plist"] = plistlib.dumps(rows); variations.append(unsafe)
        for files in variations:
            with self.subTest(extra=set(files) - set(base)):
                with self.assertRaises(AssertionError):
                    self.verify(nx_deb(files))

    def test_rejects_traversal_symlink_and_duplicate_archive_member(self):
        for name, kind in (("../escape", tarfile.REGTYPE), ("link", tarfile.SYMTYPE), ("./" + NX_TWEAK, tarfile.REGTYPE)):
            entry = tarfile.TarInfo(name); entry.type = kind; entry.linkname = "/etc/passwd"
            with self.subTest(name=name):
                with self.assertRaises(AssertionError):
                    self.verify(nx_deb(extra=entry))

    def test_bounded_decompression_and_lzma_memory_limit(self):
        module = nx_tool(self, "verify_package")
        with self.assertRaisesRegex(AssertionError, "expanded"):
            module.decompress_archive("data.tar.xz", lzma.compress(b"x" * 2000), max_output=1000)
        compressed = lzma.compress(b"small", format=lzma.FORMAT_ALONE, preset=9)
        with self.assertRaisesRegex(AssertionError, "memory|decompression"):
            module.decompress_archive("data.tar.lzma", compressed, memory_limit=1024 * 1024)

    def test_rejects_partly_unsigned_code_and_missing_second_swift_slice(self):
        files = nx_payload()
        second = bytearray(nx_thin(2))
        # Keep a structurally valid CodeDirectory but sign only its first 16 bytes.
        cd = 2048 + 20
        struct.pack_into(">I", second, cd + 32, 16)
        hash_offset = struct.unpack_from(">I", second, cd + 16)[0]
        second[cd + hash_offset:cd + hash_offset + 32] = hashlib.sha256(second[:16]).digest()
        files[NX_TWEAK] = files[NX_TWEAK][:8192] + second
        with self.assertRaisesRegex(AssertionError, "signed code range"):
            self.verify(nx_deb(files))
        files[NX_TWEAK] = nx_fat()[:8192] + nx_thin(2, swift=False)
        with self.assertRaisesRegex(AssertionError, "Swift"):
            self.verify(nx_deb(files))

    def test_rejects_empty_rootless_directories(self):
        entry = tarfile.TarInfo("./var/jb/fixtures"); entry.type = tarfile.DIRTYPE
        with self.assertRaisesRegex(AssertionError, "directory|rootless"):
            self.verify(nx_deb(extra=entry))

    def test_rejects_bad_fat_inventory_and_malformed_plist_without_traceback(self):
        files = nx_payload(); binary = bytearray(files[NX_TWEAK])
        struct.pack_into(">I", binary, 8 + 20 + 8, 4096)  # second slice overlaps first
        files[NX_TWEAK] = bytes(binary)
        with self.assertRaisesRegex(AssertionError, "overlapping FAT"):
            self.verify(nx_deb(files))
        files = nx_payload(); files[NX_BUNDLE + "Root.plist"] = b"<?xml version='1.0'?><plist><dict>"
        with self.assertRaisesRegex(AssertionError, "invalid packaged plist"):
            self.verify(nx_deb(files))

    def test_malformed_settings_object_is_a_validation_failure(self):
        module = nx_tool(self, "verify_package")
        for target in (NX_BUNDLE + "Info.plist", "Library/PreferenceLoader/Preferences/NoticeX.plist"):
            files = nx_payload(); files[target] = plistlib.dumps([])
            with self.subTest(target=target):
                try:
                    module.verify_resources(files)
                except Exception as error:
                    self.assertIsInstance(error, AssertionError, "malformed Settings must fail validation, not crash the verifier")
                    self.assertRegex(str(error), "Settings|Preferences|PreferenceLoader")
                else:
                    self.fail("malformed Settings accepted")

    def test_standalone_cli_never_discovers_adjacent_source_tests(self):
        nx_tool(self, "verify_package")
        with tempfile.TemporaryDirectory(prefix="nx-cli-", dir=__import__("os").environ.get("TMPDIR")) as folder:
            path = pathlib.Path(folder) / "original.deb"; path.write_bytes(nx_deb())
            (path.parent / "test_poison.py").write_text("raise RuntimeError('DO_NOT_DISCOVER')\n")
            result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/verify_package.py"), str(path)], cwd=folder,
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())


class NXEvidenceContract(unittest.TestCase):
    def test_compile_evidence_is_target_source_and_arch_specific(self):
        module = nx_tool(self, "ci_evidence")
        self.assertTrue(hasattr(module, "verify_compile_log"), "missing compiler graph evidence verifier")
        graph = {"NoticeX": {"architectures": ["arm64", "arm64e"],
                              "sources": [{"path": "Sources/Core/NoticePolicy.swift"}, {"path": "Sources/Native/NoticeXBootstrap.m"}]},
                 "NoticeXPrefs": {"architectures": ["arm64", "arm64e"],
                                   "sources": [{"path": "Sources/Core/NoticePolicy.swift"}, {"path": "prefs/NoticeXPreferences.swift"}]}}
        lines = []
        for target in graph:
            for arch in graph[target]["architectures"]:
                paths = " ".join(("../" + path if target == "NoticeXPrefs" and not path.startswith("prefs/") else path.removeprefix("prefs/"))
                                 for path in (entry["path"] for entry in graph[target]["sources"]) if path.endswith(".swift"))
                lines.append(f'/Xcode/usr/bin/swiftc -c -target {arch}-apple-ios15.0 -emit-module-path .theos/obj/{arch}/{target}.swiftmodule {paths}')
                if target == "NoticeX":
                    lines.append(f'/Xcode/usr/bin/clang -c -target {arch}-apple-ios15.0 -DTHEOS_INSTANCE_NAME=\\"NoticeX\\" Sources/Native/NoticeXBootstrap.m -o .theos/obj/{arch}/bootstrap.o')
                lines.append(f'==> Linking {"tweak" if target == "NoticeX" else "bundle"} {target} ({arch})...')
            lines.append(f'==> Signing {target}...')
        raw = "\n".join(lines) + "\n"
        module.verify_compile_log(raw, graph)
        continued='\n'.join(line+' \\\n| /theos/parse-swiftc-output' if '/swiftc ' in line else line
                            for line in lines)+'\n'
        forwarded=raw.replace('swiftc -c -target ',
                              'swiftc -c -Xcc -target -Xcc arm64-apple-ios15.0 -target ')
        for form,value in [('shell-continuation',continued),('forwarded-clang-target',forwarded),
                           ('both',continued.replace('swiftc -c -target ',
                              'swiftc -c -Xcc -target -Xcc arm64-apple-ios15.0 -target '))]:
            with self.subTest(form=form):
                module.verify_compile_log(value,graph)
        missing_driver=forwarded
        for arch in ('arm64','arm64e'):
            missing_driver=missing_driver.replace(' -target '+arch+'-apple-ios15.0 -emit-module-path',
                                                  ' -emit-module-path')
        with self.assertRaisesRegex(AssertionError,'compile'):
            module.verify_compile_log(missing_driver,graph)
        missing = raw.replace("Sources/Native/NoticeXBootstrap.m", "wrong.m", 1)
        with self.assertRaisesRegex(AssertionError, "compile"):
            module.verify_compile_log(missing, graph)
        wrong_owner = raw.replace("/NoticeXPrefs.swiftmodule", "/NoticeX.swiftmodule")
        with self.assertRaisesRegex(AssertionError, "compile"):
            module.verify_compile_log(wrong_owner, graph)

    def test_failed_success_validation_still_writes_failure_checksums(self):
        module = nx_tool(self, "ci_evidence")
        with tempfile.TemporaryDirectory(prefix="nx-finalize-", dir=__import__("os").environ.get("TMPDIR")) as folder:
            out = pathlib.Path(folder)
            (out / "scope.json").write_text("{}\n")
            (out / "setup.log").write_text("fixture setup failed\n")
            with self.assertRaisesRegex(AssertionError, "missing successful"):
                module.manifest(out, "success")
            self.assertTrue((out / "SHA256SUMS.txt").is_file(), "late verifier failure must retain checksums")
            report = json.loads((out / "evidence-manifest.json").read_text())
            self.assertEqual(report["job_status_before_upload"], "failure")
            self.assertIn("validation_error", report)

    def test_original_retention_and_checksum_binding_rejects_tampering(self):
        module = nx_tool(self, "ci_evidence")
        with tempfile.TemporaryDirectory(prefix="nx-evidence-", dir=__import__("os").environ.get("TMPDIR")) as folder:
            root = pathlib.Path(folder); out = root / "evidence"; out.mkdir()
            (root / "control").write_text(text("control"))
            (root / "packages").mkdir()
            name = "com.tsangbaby.noticex_0.1.0-beta3_iphoneos-arm64e.deb"
            original = root / "packages" / name; original.write_bytes(nx_deb())
            # Deliberately synthetic provenance for this isolated unit fixture only.
            scope = {"source_sha": "a" * 40, "repository": "Tsangbaby/Notice-X", "run_id": "12", "attempt": "1",
                     "scheme": "roothide", "device_tested": False}
            (out / "scope.json").write_text(json.dumps(scope))
            (out / "SOURCE_COMMIT.txt").write_text(scope["source_sha"] + "\n")
            (out / "SOURCE_REPOSITORY.txt").write_text(scope["repository"] + "\n")
            (out / "theos-build.log").write_text("synthetic fixture, not compiler evidence\n")
            retained = module.retain(root, out)
            self.assertEqual(retained["sha256"], hashlib.sha256(original.read_bytes()).hexdigest())
            self.assertEqual(retained["build_log_sha256"], hashlib.sha256((out / "theos-build.log").read_bytes()).hexdigest())
            self.assertEqual((out / name).read_bytes(), original.read_bytes())
            module.manifest(out, "failure")
            module.verify_evidence(out, scope)
            (out / "SOURCE_COMMIT.txt").write_text("b" * 40 + "\n")
            module.manifest(out, "failure")
            with self.assertRaisesRegex(AssertionError, "source marker"):
                module.verify_evidence(out, scope)
            (out / "SOURCE_COMMIT.txt").write_text(scope["source_sha"] + "\n")
            module.manifest(out, "failure")
            (out / "theos-build.log").write_text("tampered\n")
            with self.assertRaisesRegex(AssertionError, "checksum"):
                module.verify_evidence(out, scope)
            self.assertEqual((out / name).read_bytes(), original.read_bytes())


if __name__ == "__main__":
    unittest.main()
