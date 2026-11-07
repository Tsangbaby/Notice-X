from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = "ef406c8bbdb6a63df44d9f09481de71d1172142c"


class BannerSessionContracts(unittest.TestCase):
    def test_native_resolver_requires_live_session_before_private_ui_reads(self):
        source = (ROOT / "Sources/Native/NoticeXBootstrap.m").read_text()
        header = (ROOT / "Sources/Native/NoticeXBridge.h").read_text()
        signature = "NXResolveBannerParts(id owner, BOOL hasActiveBannerSession)"
        self.assertIn(signature, source)
        self.assertIn(signature, header)
        body = source.split(signature, 1)[1].split("static void NXImageAdded", 1)[0]
        self.assertIn("if (!hasActiveBannerSession)", body)
        self.assertLess(body.index("if (!hasActiveBannerSession)"), body.index("NXUnlockedHomeOrApp()"))
        self.assertLess(body.index("if (!hasActiveBannerSession)"), body.index("NXObjectGetter(owner"))

    def test_only_exact_1541_uses_lifecycle_authority_and_other_os_keeps_look_filter(self):
        source = (ROOT / "Sources/Native/NoticeXBootstrap.m").read_text()
        self.assertIn("static BOOL NXLifecycleOwnsBannerIdentity(void)", source)
        authority = source.split("static BOOL NXLifecycleOwnsBannerIdentity(void)", 1)[1].split("NXBannerParts *NXResolve", 1)[0]
        self.assertIn("dispatch_once", authority)
        self.assertIn("os.majorVersion == 15 && os.minorVersion == 4 && os.patchVersion == 1", authority)
        body = source.split("if (!NXLifecycleOwnsBannerIdentity())", 1)[1].split("id request =", 1)[0]
        self.assertIn("NXReadBool(look, @selector(_isBanner), &banner)", body)
        self.assertIn("if (!banner)", body)
        self.assertIn("return nil;", body)
        for guard in ("@selector(isCriticalAlert)", "content isDescendantOfView:material",
                      "material isDescendantOfView:look", "content isDescendantOfView:look"):
            self.assertIn(guard, source)

    def test_caller_derives_admission_from_same_owner_not_literal_true(self):
        source = (ROOT / "Sources/UI/NoticeBannerCoordinator.swift").read_text()
        self.assertIn("let hasActiveBannerSession = context.owner === owner && !context.ending", source)
        self.assertIn("NXResolveBannerParts(owner, hasActiveBannerSession)", source)
        self.assertNotIn("NXResolveBannerParts(owner, true)", source)
        self.assertLess(source.index("guard !context.ending, !context.installing"),
                        source.index("let hasActiveBannerSession ="))

    def test_admission_commit_preserved_callbacks_visuals_preferences_and_policy(self):
        # Preserve the original admission-only claim at its frozen commit.
        admission = '8328ac1720189a4eb382cf1495712fcec004394e'
        for path in ("Sources/Runtime/NoticeRuntime.swift", "Sources/UI/NoticeCardAnimator.swift",
                     "Sources/Core/NoticePolicy.swift", "Sources/Support/NoticePreferences.swift",
                     "prefs/NoticeXPreferences.swift"):
            old = subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT, text=True)
            frozen = subprocess.check_output(["git", "show", admission + ":" + path], cwd=ROOT, text=True)
            self.assertEqual(frozen, old, path)

    def test_native_host_replays_target_and_two_unchanged_os_lanes(self):
        runner = (ROOT / "tests/run_native_tests.py").read_text()
        host = (ROOT / "tests/Native/native_host.m").read_text()
        for lane in ("15.4.1", "15.4.0", "16.0.3"):
            self.assertIn(lane, runner)
        self.assertIn("lifecycle admits target banner when look flag is false", host)
        self.assertIn("nonbanner without live session remains excluded", host)
        self.assertIn("OS authority is cached once", host)


if __name__ == "__main__":
    unittest.main()
