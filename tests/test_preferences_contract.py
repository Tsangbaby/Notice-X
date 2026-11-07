from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class PreferencesContracts(unittest.TestCase):
    def test_only_real_boolean_preferences_can_enable_the_tweak(self):
        source=(ROOT/'Sources/Core/NoticePolicy.swift').read_text()
        self.assertIn('struct NXConfiguration',source,'missing default-off typed configuration')
        self.assertIn('CFBooleanGetTypeID()',source,'numeric preferences must not enable hooks')
        self.assertIn('enum NXPreferenceTransaction',source,'save must precede notification')

if __name__=='__main__':unittest.main()
