from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class RuntimeContracts(unittest.TestCase):
    def test_disappearance_cleanup_cannot_retire_a_reentrant_replacement(self):
        source=(ROOT/'Sources/Runtime/NoticeRuntime.swift').read_text()
        start='private let nxDidDisappearCallback: NXReasonCallback = '
        end='private let nxWillNotAppearCallback: NXReasonCallback = '
        self.assertEqual(source.count(start),1,'unique disappearance callback')
        self.assertEqual(source.count(end),1,'unique next callback boundary')
        body=source.split(start,1)[1].split(end,1)[0]
        retire='NXBannerCoordinator.shared.retire(owner)'
        forward='unsafeBitCast(previous,to:NXReasonCallback.self)(owner,selector,presentable,reason)'
        self.assertEqual(body.count(retire),1,'exactly one old-session retirement')
        self.assertEqual(body.count(forward),1,'exactly one unchanged native forwarding')
        self.assertLess(body.index(retire),body.index(forward),
                        'old disappearance must retire before native code can install a replacement')

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
