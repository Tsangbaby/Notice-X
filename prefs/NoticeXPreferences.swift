import Foundation
import CoreFoundation
import UIKit

@objc(NXSettingsController)
final class NXSettingsController: PSListController {
    private var loadedSpecifiers: NSMutableArray?

    override init(nibName:String?,bundle:Bundle?) {
        super.init(nibName:nibName,bundle:bundle)
    }
    required init?(coder:NSCoder) { super.init(coder:coder) }

    // Some PreferenceLoader factories prefer this selector. Never forward it to a private super.
    @objc(initForContentSize:)
    convenience init(contentSize:CGSize) {
        self.init(nibName:nil,bundle:nil)
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "Notice-X"
    }

    override var specifiers: NSMutableArray! {
        get {
            if let loaded = loadedSpecifiers { return loaded }
            let loaded = loadSpecifiers(fromPlistName:"Root",target:self) ?? NSMutableArray()
            let resources = Bundle(for:NXSettingsController.self)
            for case let specifier as PSSpecifier in loaded {
                for key in ["label","footerText"] {
                    if let value = specifier.property(forKey:key) as? String {
                        specifier.setProperty(resources.localizedString(forKey:value,value:value,table:"Root"),forKey:key)
                    }
                }
            }
            loadedSpecifiers = loaded
            super.specifiers = loaded
            return loaded
        }
        set { loadedSpecifiers = newValue; super.specifiers = newValue }
    }

    override func readPreferenceValue(_ specifier:PSSpecifier!) -> Any! {
        guard specifier?.property(forKey:"key") as? String == NXPreferences.key else { return nil }
        return NSNumber(value:NXPreferences.read().enabled)
    }

    override func setPreferenceValue(_ value:Any!,specifier:PSSpecifier!) {
        guard let specifier = specifier,
              specifier.property(forKey:"key") as? String == NXPreferences.key,
              let number = value as? NSNumber,
              CFGetTypeID(number) == CFBooleanGetTypeID() else { return }
        if !NXPreferences.saveEnabled(number.boolValue) { reloadSpecifier(specifier) }
    }
}
