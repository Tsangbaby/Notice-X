from pathlib import Path
import plistlib
import unittest

ROOT=Path(__file__).resolve().parents[1]

class SettingsContracts(unittest.TestCase):
    def test_one_default_off_switch_has_real_swift_persistence_and_localization(self):
        controller=ROOT/'prefs/NoticeXPreferences.swift'
        root=ROOT/'prefs/Resources/Root.plist'
        self.assertTrue(controller.is_file() and root.is_file(),'missing working Swift Settings page')
        text=controller.read_text()
        self.assertIn('NXSettingsController: PSListController',text)
        self.assertIn('NXPreferences.saveEnabled',text)
        rows=plistlib.loads(root.read_bytes())['items']
        controls=[r for r in rows if 'key' in r]
        self.assertEqual(len(controls),1)
        self.assertEqual(controls[0]['key'],'enabled')
        self.assertIs(controls[0]['default'],False)
        self.assertNotIn('PostNotification',controls[0], 'Swift transaction owns exactly one notification after save')
        for language in ['en','zh-Hans']:
            values=plistlib.loads((ROOT/f'prefs/Resources/{language}.lproj/Root.strings').read_bytes())
            for row in rows:
                for field in ['label','footerText']:
                    if field in row:self.assertIn(row[field],values)
        entry=plistlib.loads((ROOT/'layout/Library/PreferenceLoader/Preferences/NoticeX.plist').read_bytes())['entry']
        info=plistlib.loads((ROOT/'prefs/Resources/Info.plist').read_bytes())
        self.assertEqual(entry['detail'],'NXSettingsController')
        self.assertEqual(info['NSPrincipalClass'],'NXSettingsController')
        bridge=(ROOT/'prefs/NoticeXPreferencesBridge.h').read_text()
        self.assertNotIn('initForContentSize',bridge,'do not synthesize forwarding to an unsupported private initializer')
        self.assertIn('@objc(initForContentSize:)',text,'own the legacy factory adapter through a supported UIKit initializer')

if __name__=='__main__':unittest.main()
