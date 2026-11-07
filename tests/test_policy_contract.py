from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'Sources/Core/NoticePolicy.swift'

class PolicyContracts(unittest.TestCase):
    def test_motion_uses_the_accepted_glint_timing_not_a_new_spring_family(self):
        self.assertTrue(POLICY.is_file(), 'missing Swift motion and admission policy')
        source = POLICY.read_text()
        expected = {'openDuration':0.6, 'openDamping':0.72, 'openVelocity':0.4,
                    'contentDuration':0.55, 'contentDelay':0.1, 'contentDamping':0.8,
                    'contentScale':0.94, 'contentOffsetY':-14.0,
                    'closeDuration':0.6, 'closeDamping':1.0}
        for name, value in expected.items():
            matches = re.findall(r'static let '+name+r'(?:\s*:\s*\w+)?\s*=\s*(-?[0-9.]+)',source)
            self.assertEqual(len(matches),1,name)
            self.assertEqual(float(matches[0]),value,name)
        for unsupported in ('import UIKit','import SwiftUI','import Orion'):
            self.assertNotIn(unsupported,source)

    def test_banner_admission_and_generation_ownership_are_explicit(self):
        source = POLICY.read_text()
        self.assertIn('struct NXAdmission',source,'missing banner-only admission')
        self.assertIn('struct NXSession',source,'missing per-banner generation owner')
        self.assertIn('guard token == generation',source,'stale callback may retire a newer owner')

if __name__=='__main__':unittest.main()
