from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]

class VisualContracts(unittest.TestCase):
    def test_historical_beta2_mask_never_changed_native_banner_geometry(self):
        path=ROOT/'Sources/UI/NoticeCardAnimator.swift'
        self.assertTrue(path.is_file(),'missing owned card reveal animator')
        # Device-rejected historical mechanism, not the current reveal requirement.
        text=subprocess.check_output(['git','show',
            '8328ac1720189a4eb382cf1495712fcec004394e:Sources/UI/NoticeCardAnimator.swift'],
            cwd=ROOT,text=True)
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
