import Foundation
import CoreFoundation
import ObjectiveC
import UIKit

private var nxBannerContextKey: UInt8 = 0

private final class NXBannerContext: NSObject {
    weak var owner: AnyObject?
    var animator: NXCardAnimator?
    var ending = false
    var installing = false
    init(owner:AnyObject) { self.owner = owner }
    deinit { animator?.restore() }
}

/// Native banner scheduling remains Apple's. We own only one local visual session per presentable.
final class NXBannerCoordinator {
    static let shared = NXBannerCoordinator()
    private var configuration = NXConfiguration(enabledValue:nil)
    private var started = false
    private let contexts = NSHashTable<NXBannerContext>.weakObjects()
    private var accessibilityObservers: [NSObjectProtocol] = []

    func start() {
        guard Thread.isMainThread, !started else { return }
        started = true
        configuration = NXPreferences.read()
        let pointer = Unmanaged.passUnretained(self).toOpaque()
        let center = CFNotificationCenterGetDarwinNotifyCenter()
        for name in [NXPreferences.changed,"com.apple.springboard.lockstate"] {
            CFNotificationCenterAddObserver(center,pointer,nxPreferencesChanged,
                                             name as CFString,nil,.deliverImmediately)
        }
        accessibilityObservers.append(NotificationCenter.default.addObserver(
            forName:UIAccessibility.reduceMotionStatusDidChangeNotification,
            object:nil,queue:.main) { [weak self] _ in self?.cancelAll() })
        accessibilityObservers.append(NotificationCenter.default.addObserver(
            forName:UIAccessibility.reduceTransparencyStatusDidChangeNotification,
            object:nil,queue:.main) { [weak self] _ in self?.cancelAll() })
    }

    func configurationChanged() {
        guard Thread.isMainThread else { return }
        configuration = NXPreferences.read()
        // A lock or Settings change retires current surfaces; do not restyle mid-interaction.
        cancelAll()
    }

    func willAppear(_ owner:AnyObject) {
        guard Thread.isMainThread else { return }
        retire(owner)
        guard configuration.enabled, NXUnlockedHomeOrApp() else { return }
        let context = NXBannerContext(owner:owner)
        objc_setAssociatedObject(owner,&nxBannerContextKey,context,.OBJC_ASSOCIATION_RETAIN_NONATOMIC)
        contexts.add(context)
    }

    func didAppear(_ owner:AnyObject) {
        guard Thread.isMainThread, let context = context(owner), !context.ending else { return }
        layout(owner)
        context.animator?.open()
    }

    func layout(_ owner:AnyObject) {
        guard Thread.isMainThread, let context = context(owner),
              !context.ending, !context.installing else { return }
        guard configuration.enabled, NXUnlockedHomeOrApp(),
              let parts = NXResolveBannerParts(owner) else {
            if context.animator != nil { retire(owner) }
            return
        }
        if let animator = context.animator {
            guard animator.matches(parts) else { retire(owner); return }
            animator.layout()
            return
        }
        let bounds = parts.look.bounds
        let admission = NXAdmission(enabled:configuration.enabled,unlocked:true,banner:true,
                                    onMainThread:Thread.isMainThread,attached:parts.look.window != nil,
                                    hasForeignMask:parts.look.mask != nil,
                                    width:Double(bounds.width),height:Double(bounds.height))
        guard admission.allowed else { return }
        // Publish the installation frontier before UIKit setters can synchronously reenter layout.
        context.installing = true
        let animator = NXCardAnimator(parts:parts)
        context.installing = false
        guard self.context(owner) === context, !context.ending else { animator?.restore(); return }
        context.animator = animator
        // Start as soon as a real attached surface is ready; never leave hidden content waiting
        // indefinitely for a second private lifecycle callback.
        animator?.open()
    }

    func willDisappear(_ owner:AnyObject) {
        guard Thread.isMainThread, let context = context(owner) else { return }
        context.ending = true
        context.animator?.close()
    }

    func retire(_ owner:AnyObject) {
        guard Thread.isMainThread, let context = context(owner) else { return }
        // Reentry must see no active owner before restore touches UIKit.
        objc_setAssociatedObject(owner,&nxBannerContextKey,nil,.OBJC_ASSOCIATION_RETAIN_NONATOMIC)
        contexts.remove(context)
        context.ending = true
        context.animator?.restore()
        context.animator = nil
    }

    private func cancelAll() {
        guard Thread.isMainThread else { return }
        for context in contexts.allObjects {
            if let owner = context.owner { retire(owner) }
        }
    }

    private func context(_ owner:AnyObject) -> NXBannerContext? {
        objc_getAssociatedObject(owner,&nxBannerContextKey) as? NXBannerContext
    }
}

private func nxPreferencesChanged(_ center:CFNotificationCenter?,_ observer:UnsafeMutableRawPointer?,
                                  _ name:CFNotificationName?,_ object:UnsafeRawPointer?,
                                  _ userInfo:CFDictionary?) {
    guard observer != nil else { return }
    // The observer belongs to the process-lifetime singleton; callbacks only enqueue main work.
    DispatchQueue.main.async { NXBannerCoordinator.shared.configurationChanged() }
}
