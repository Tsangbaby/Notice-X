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
    var nativeAppeared = false
    var openingScheduled = false
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
        if configuration.enabled { NXDiagnostic.record(.runtimeSwitchOn) }
        else { NXDiagnostic.record(.runtimeSwitchOff) }
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
        if configuration.enabled { NXDiagnostic.record(.runtimeSwitchOn) }
        else { NXDiagnostic.record(.runtimeSwitchOff) }
        // A lock or Settings change retires current surfaces; do not restyle mid-interaction.
        cancelAll()
    }

    func willAppear(_ owner:AnyObject) {
        guard Thread.isMainThread else { return }
        NXDiagnostic.record(.bannerWillAppear)
        retire(owner)
        guard configuration.enabled else { NXDiagnostic.record(.bannerSwitchOff); return }
        guard NXUnlockedHomeOrApp() else { NXDiagnostic.record(.bannerContextRejected); return }
        NXDiagnostic.record(.bannerContextReady)
        let context = NXBannerContext(owner:owner)
        objc_setAssociatedObject(owner,&nxBannerContextKey,context,.OBJC_ASSOCIATION_RETAIN_NONATOMIC)
        contexts.add(context)
        NXDiagnostic.record(.bannerSessionCreated)
        // One bounded escape hatch, not a polling loop or a second animation clock.
        DispatchQueue.main.asyncAfter(deadline:.now()+1.5) { [weak self, weak context, weak owner] in
            guard let self = self, let context = context, let owner = owner,
                  self.context(owner) === context, !context.ending,
                  !context.openingScheduled else { return }
            self.retire(owner)
        }
    }

    func didAppear(_ owner:AnyObject) {
        NXDiagnostic.record(.bannerDidAppear)
        guard Thread.isMainThread, let context = context(owner), !context.ending else { return }
        context.nativeAppeared = true
        layout(owner)
    }

    func layout(_ owner:AnyObject) {
        guard Thread.isMainThread else { return }
        guard let context = context(owner) else { NXDiagnostic.record(.layoutWithoutSession); return }
        guard !context.ending, !context.installing else { NXDiagnostic.record(.layoutSessionBusy); return }
        let hasActiveBannerSession = context.owner === owner && !context.ending
        guard configuration.enabled, NXUnlockedHomeOrApp(),
              let parts = NXResolveBannerParts(owner, hasActiveBannerSession) else {
            NXDiagnostic.record(.layoutContextRejected)
            if context.animator != nil { retire(owner) }
            return
        }
        if let animator = context.animator {
            guard animator.matches(parts) else {
                NXDiagnostic.record(.visualIdentityRejected); retire(owner); return
            }
            NXDiagnostic.record(.visualReused)
            animator.layout()
            scheduleOpen(owner,context:context)
            return
        }
        let bounds = parts.look.bounds
        let admission = NXAdmission(enabled:configuration.enabled,unlocked:true,banner:true,
                                    onMainThread:Thread.isMainThread,attached:parts.look.window != nil,
                                    hasForeignMask:parts.look.mask != nil,
                                    width:Double(bounds.width),height:Double(bounds.height))
        guard admission.allowed else { NXDiagnostic.record(.admissionRejected); return }
        NXDiagnostic.record(.admissionReady)
        // Publish the installation frontier before UIKit setters can synchronously reenter layout.
        context.installing = true
        let animator = NXCardAnimator(parts:parts)
        context.installing = false
        guard self.context(owner) === context, !context.ending else {
            NXDiagnostic.record(.visualSessionReplaced); animator?.restore(); return
        }
        context.animator = animator
        if animator == nil { NXDiagnostic.record(.visualConstructorRejected) }
        else { NXDiagnostic.record(.visualInstalled) }
        scheduleOpen(owner,context:context)
    }

    private func scheduleOpen(_ owner:AnyObject, context:NXBannerContext) {
        guard context.nativeAppeared, !context.openingScheduled,
              !context.ending, context.animator != nil else { return }
        context.openingScheduled = true
        // Run outside native transition completion/layout transactions. Do not replay native entry.
        DispatchQueue.main.async { [weak self, weak context, weak owner] in
            guard let self = self, let context = context, let owner = owner,
                  self.context(owner) === context, !context.ending,
                  context.nativeAppeared, self.configuration.enabled else { return }
            self.layout(owner)
            guard self.context(owner) === context, !context.ending else { return }
            context.animator?.open()
        }
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
