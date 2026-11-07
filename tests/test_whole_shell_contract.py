from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = '8328ac1720189a4eb382cf1495712fcec004394e'


class WholeShellContracts(unittest.TestCase):
    def test_reveal_moves_one_real_shell_instead_of_masking_native_banner(self):
        source = (ROOT / 'Sources/UI/NoticeCardAnimator.swift').read_text()
        self.assertNotIn('maskView', source, 'device-rejected animated-mask mechanism must be removed')
        self.assertIn('self.shell.frame = self.bounds', source)
        self.assertIn('self.shell.layoutIfNeeded()', source)
        self.assertIn('snapshotView.frame = contentFrame', source)
        self.assertNotIn('content?.transform =', source)
        self.assertNotIn('look.frame =', source)
        self.assertNotIn('look.transform =', source)
        self.assertNotRegex(source, r'look\.mask\s*=(?!=)')
        for forbidden in ('UIWindow(', 'addGestureRecognizer', 'CADisplayLink', 'scheduledTimer'):
            self.assertNotIn(forbidden, source)

    def test_native_did_appear_is_required_before_queued_reveal(self):
        source = (ROOT / 'Sources/UI/NoticeBannerCoordinator.swift').read_text()
        self.assertIn('var nativeAppeared = false', source)
        self.assertIn('context.nativeAppeared = true', source)
        self.assertIn('private func scheduleOpen', source)
        body = source.split('private func scheduleOpen', 1)[1].split('func willDisappear', 1)[0]
        self.assertIn('context.nativeAppeared', body)
        self.assertIn('DispatchQueue.main.async', body)
        self.assertIn('self.context(owner) === context', body)
        self.assertEqual(source.count('.open()'), 1)
        self.assertIn('DispatchQueue.main.asyncAfter', source, 'missing preparation escape hatch')

    def test_open_revalidates_geometry_after_native_preparation(self):
        source = (ROOT / 'Sources/UI/NoticeCardAnimator.swift').read_text()
        body = source.split('func open()', 1)[1].split('let token =', 1)[0]
        self.assertIn('NXAdmission(', body)
        self.assertIn('guard admission.allowed else { restore(); return }', body)

    def test_native_preparation_cannot_inherit_an_entry_alpha_animation(self):
        source = (ROOT / 'Sources/UI/NoticeCardAnimator.swift').read_text()
        body = source.split('init?(parts:', 1)[1].split('private var compact:', 1)[0]
        self.assertIn('UIView.performWithoutAnimation {', body)
        self.assertLess(body.index('UIView.performWithoutAnimation {'), body.index('content.alpha = 0'))


if __name__ == '__main__':
    unittest.main()
