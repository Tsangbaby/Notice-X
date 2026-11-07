import Foundation
import CoreFoundation

/// Accepted Glint 9b07183 card timings, not a second animation family.
enum NXMotion {
    static let openDuration: Double = 0.6
    static let openDamping: Double = 0.72
    static let openVelocity: Double = 0.4
    static let contentDuration: Double = 0.55
    static let contentDelay: Double = 0.1
    static let contentDamping: Double = 0.8
    static let contentScale: Double = 0.94
    static let contentOffsetY: Double = -14.0
    static let closeDuration: Double = 0.6
    static let closeDamping: Double = 1.0
}

struct NXAdmission {
    let enabled: Bool
    let unlocked: Bool
    let banner: Bool
    let onMainThread: Bool
    let attached: Bool
    let hasForeignMask: Bool
    let width: Double
    let height: Double

    var allowed: Bool {
        enabled && unlocked && banner && onMainThread && attached && !hasForeignMask &&
            width.isFinite && height.isFinite && width >= 80 && height >= 24 &&
            width <= 1400 && height <= 600
    }
}

enum NXPhase: Equatable { case idle, opening, visible, closing }

/// Only the current per-controller generation may finish its own visual work.
struct NXSession {
    private(set) var generation: UInt64 = 0
    private(set) var phase: NXPhase = .idle

    mutating func begin(_ phase: NXPhase) -> UInt64 {
        generation &+= 1
        self.phase = phase
        return generation
    }

    @discardableResult
    mutating func finish(_ token: UInt64, from expected: NXPhase, to next: NXPhase) -> Bool {
        guard token == generation, phase == expected else { return false }
        phase = next
        return true
    }

    mutating func invalidate() {
        generation &+= 1
        phase = .idle
    }
}

struct NXConfiguration {
    let enabled: Bool
    init(enabledValue: Any?) {
        guard let number = enabledValue as? NSNumber,
              CFGetTypeID(number) == CFBooleanGetTypeID() else {
            enabled = false
            return
        }
        enabled = number.boolValue
    }
}

enum NXPreferenceTransaction {
    static func save(_ enabled: Bool, read: () -> Any?, write: (Any?) -> Void,
                     synchronize: () -> Bool, notify: () -> Void) -> Bool {
        let previous = read()
        write(NSNumber(value: enabled))
        guard synchronize() else {
            write(previous)
            _ = synchronize()
            return false
        }
        notify()
        return true
    }
}
