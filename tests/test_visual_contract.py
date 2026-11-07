from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class VisualContracts(unittest.TestCase):
    def test_owned_mask_not_native_banner_geometry_drives_the_glint_reveal(self):
        path=ROOT/'Sources/UI/NoticeCardAnimator.swift'
        self.assertTrue(path.is_file(),'missing owned card reveal animator')
        text=path.read_text()
        for required in ('UIVisualEffectView','UISpringTimingParameters','NXMotion.openDamping',
                         'NXMotion.closeDamping','look.mask = maskView','state.invalidate()',
                         'stopAnimation(true)','UIAccessibility.isReduceMotionEnabled'):
            self.assertIn(required,text)
        for forbidden in ('look.frame =','look.transform =','UIWindow','CADisplayLink',
                          'scheduledTimer','removeAllAnimations','addGestureRecognizer'):
            self.assertNotIn(forbidden,text)
        self.assertIn('look.mask === maskView',text)
        self.assertIn('isUserInteractionEnabled = false',text)
        self.assertIn('compact.height * 0.5',text)

if __name__=='__main__':unittest.main()
