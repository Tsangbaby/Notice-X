import Foundation
import CoreFoundation

/// Shared Settings/SpringBoard adapter. No preference reads in animation frames.
enum NXPreferences {
    static let domain = "com.tsangbaby.noticex"
    static let changed = "com.tsangbaby.noticex/reload"
    static let key = "enabled"

    static func read() -> NXConfiguration {
        CFPreferencesAppSynchronize(domain as CFString)
        return NXConfiguration(enabledValue:CFPreferencesCopyAppValue(key as CFString,domain as CFString))
    }

    @discardableResult
    static func saveEnabled(_ enabled: Bool) -> Bool {
        NXPreferenceTransaction.save(enabled,
            read:{ CFPreferencesCopyAppValue(key as CFString,domain as CFString) },
            write:{ value in
                CFPreferencesSetAppValue(key as CFString,value as CFPropertyList?,domain as CFString)
            },
            synchronize:{ CFPreferencesAppSynchronize(domain as CFString) },
            notify:{
                CFNotificationCenterPostNotification(CFNotificationCenterGetDarwinNotifyCenter(),
                    CFNotificationName(changed as CFString),nil,nil,true)
            })
    }
}
