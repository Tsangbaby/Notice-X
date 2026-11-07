from pathlib import Path
import plistlib
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC_VERSION = "0.1.0-beta1+diag1"
DIAGNOSTIC_DOMAIN = "com.tsangbaby.noticex.diag1541"


class DiagnosticContracts(unittest.TestCase):
    def diagnostic_source(self):
        path = ROOT / "Sources/Native/NoticeXDiagnostics.m"
        self.assertTrue(path.is_file(), "missing bounded diagnostic producer")
        return path.read_text()

    def test_burst_markers_use_one_bounded_drain_not_one_write_per_callback(self):
        source = self.diagnostic_source()
        self.assertIn("NXBufferedCodes[96]", source)
        self.assertIn("NXDrainScheduled", source)
        self.assertIn("static void NXDrain", source)
        self.assertNotIn("NXPending >= NXMaxPending || NXAccepted", source)

    def test_diagnostic_candidate_is_versioned_and_in_runtime_graph(self):
        makefile = (ROOT / "Makefile").read_text()
        control = (ROOT / "control").read_text()
        verifier = (ROOT / "tools/verify_package.py").read_text()
        self.assertIn("Sources/Support/NoticeDiagnostics.swift", makefile)
        self.assertIn("Sources/Native/NoticeXDiagnostics.m", makefile)
        self.assertIn("Version: " + DIAGNOSTIC_VERSION, control)
        self.assertIn('"Version": "' + DIAGNOSTIC_VERSION + '"', verifier)

    def test_diagnostic_sink_is_bounded_and_separate_from_product_preferences(self):
        source = self.diagnostic_source()
        self.assertIn(DIAGNOSTIC_DOMAIN, source)
        self.assertIn('@"snapshot"', source)
        self.assertIn("NXMaxEvents = 96", source)
        self.assertIn("NXMaxPending = 32", source)
        self.assertIn("NXMaxBytes = 16384", source)
        self.assertIn("CFPreferencesSetAppValue", source)
        self.assertIn("CFPreferencesAppSynchronize", source)
        self.assertIn("CFPreferencesCopyAppValue", source)
        self.assertIn("dispatch_queue_create", source)
        self.assertIn("CFEqual", source)
        self.assertIn("CFPropertyListCreateData", source)
        self.assertNotIn("%@", source)
        for forbidden in ("notificationText", "userInfo", "payload", "Bundle.main", "absolutePath", "description"):
            self.assertNotIn(forbidden, source)
        self.assertIn("@finally", source)
        self.assertIn("pthread_mutex_lock", source)
        self.assertIn("NXReleaseReservation", source)

    def test_diagnostic_vocabulary_is_fixed_and_native_bridge_is_numeric(self):
        source = self.diagnostic_source()
        adapter = (ROOT / "Sources/Support/NoticeDiagnostics.swift").read_text()
        bridge = (ROOT / "Sources/Native/NoticeXBridge.h").read_text()
        native = (ROOT / "Sources/Native/NoticeXBootstrap.m").read_text()
        self.assertIn("enum Phase: Int32", adapter)
        self.assertIn("void NXDiagnosticRecord(int32_t code)", source)
        self.assertIn("NXDiagnosticRecord", bridge)
        for phase in (
            "runtime_start", "install_class_missing", "install_abi_mismatch",
            "install_complete", "runtime_switch_on", "runtime_switch_off",
            "banner_will_appear", "banner_context_rejected", "banner_context_ready",
            "resolve_classes_missing", "resolve_not_banner", "resolve_critical_alert",
            "resolve_hierarchy_rejected", "resolve_ready", "admission_rejected",
            "admission_ready", "visual_constructor_rejected", "visual_installed",
        ):
            self.assertIn('"' + phase + '"', source)
        self.assertIn("NXDiagnosticNativeCode", bridge)
        self.assertIn("NXDiagnosticRecord(NXDiagnosticNativeCode", native)

    def test_diagnostic_is_observational_and_does_not_add_action_hooks(self):
        runtime = (ROOT / "Sources/Runtime/NoticeRuntime.swift").read_text()
        coordinator = (ROOT / "Sources/UI/NoticeBannerCoordinator.swift").read_text()
        native = (ROOT / "Sources/Native/NoticeXBootstrap.m").read_text()
        combined = runtime + coordinator + native
        self.assertIn("NXDiagnostic.begin()", runtime)
        self.assertIn("NXDiagnostic.record(.runtimeSwitchOn)", coordinator)
        self.assertIn("NXDiagnostic.record(.runtimeSwitchOff)", coordinator)
        for forbidden in (
            "postNotificationRequest:", "_handleTapOnView:", "executeAction:",
            "launchApplicationWithIdentifier", "UNNotificationResponse",
            "setOptions:", "_updateOption:forKey:", "dismissPresentable",
            "FBSystemService", "interceptUpdateWithNewSettings",
        ):
            self.assertNotIn(forbidden, combined)
        self.assertEqual(runtime.count("NXDiagnostic.begin()"), 1)

    def test_package_entry_remains_the_same_settings_bundle(self):
        entry = plistlib.loads(
            (ROOT / "layout/Library/PreferenceLoader/Preferences/NoticeX.plist").read_bytes()
        )["entry"]
        self.assertEqual(entry["bundle"], "NoticeXPrefs")
        self.assertEqual(entry["detail"], "NXSettingsController")
        self.assertIs(entry.get("isController"), True)

    def test_callbacks_and_visual_policy_preserve_the_rejected_functional_baseline(self):
        baseline = "f7d5dd37582b86a928c631d14b763865268a5e50"
        def old(path):
            return subprocess.check_output(["git", "show", baseline + ":" + path], cwd=ROOT, text=True)
        for path in ("Sources/UI/NoticeCardAnimator.swift", "Sources/Core/NoticePolicy.swift",
                     "Sources/Support/NoticePreferences.swift", "prefs/NoticeXPreferences.swift"):
            self.assertEqual((ROOT / path).read_text(), old(path), path)
        path = "Sources/Runtime/NoticeRuntime.swift"
        def callbacks(text):
            return text.split("private let nxWillAppearCallback:", 1)[1].split("private enum NXRuntime", 1)[0]
        current = callbacks((ROOT / path).read_text())
        current = re.sub(r"(?m)^    NXDiagnostic\.record\(\.\w+\)\n", "", current)
        self.assertEqual(current, callbacks(old(path)), "native callback ordering/forwarding changed")
        path = "Sources/Native/NoticeXBootstrap.m"
        expression = r"NX(?:ObjectGetter|ReadBool)\([^;\n]+?\)"
        self.assertEqual(re.findall(expression, (ROOT / path).read_text()),
                         re.findall(expression, old(path)), "private getter order/count changed")

    def test_diagnostic_host_gate_executes_actual_bounded_producer_and_strict_decode(self):
        runner = (ROOT / "tests/run_swift_tests.py").read_text()
        self.assertIn("run_diagnostic", runner)
        source = self.diagnostic_source()
        self.assertIn("NX_DIAGNOSTIC_HOST_TEST", source)
        self.assertIn("os.majorVersion != 15 || os.minorVersion != 4 || os.patchVersion != 1", source)
        decoder = ROOT / "tools/read_diagnostic.py"
        self.assertTrue(decoder.is_file(), "missing strict raw-device diagnostic reader")


if __name__ == "__main__":
    unittest.main()
