from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class RuntimeContracts(unittest.TestCase):
    def test_native_banner_lifecycle_is_observed_without_replacing_notification_actions(self):
        runtime=ROOT/'Sources/Runtime/NoticeRuntime.swift'
        bridge=ROOT/'Sources/Native/NoticeXBootstrap.m'
        self.assertTrue(runtime.is_file() and bridge.is_file(),'missing actual banner lifecycle adapter')
        source=runtime.read_text(); native=bridge.read_text()
        for selector in ('presentableWillAppearAsBanner:', 'presentableDidAppearAsBanner:',
                         'presentableWillDisappearAsBanner:withReason:',
                         'presentableDidDisappearAsBanner:withReason:',
                         'presentableWillNotAppearAsBanner:withReason:',
                         'userInteractionWillBeginForBannerForPresentable:',
                         'longLookWillPresentForNotificationViewController:'):
            self.assertIn(selector,source)
        for forbidden in ('postNotificationRequest:', '_handleTapOnView:', 'executeAction:',
                          'launchApplicationWithIdentifier', 'UNNotificationResponse', 'import Orion'):
            self.assertNotIn(forbidden,source+native)
        self.assertIn('@selector(_isBanner)',native)
        self.assertIn('@selector(isCriticalAlert)',native)
        self.assertIn('sharedInstanceIfExists',native)
        self.assertIn('isUIUnlocking',native)
        self.assertIn('isPresented',native)
        self.assertIn('@catch',native)
        self.assertIn('method_getNumberOfArguments',source)
        self.assertIn('method_copyArgumentType',source)
        self.assertIn('MSHookMessageEx',source)

if __name__=='__main__':unittest.main()
