import Foundation
import ObjectiveC

private typealias NXObjectCallback = @convention(c) (AnyObject, Selector, AnyObject?) -> Void
private typealias NXReasonCallback = @convention(c) (AnyObject, Selector, AnyObject?, AnyObject?) -> Void
private typealias NXLayoutCallback = @convention(c) (AnyObject, Selector) -> Void

private enum NXHookMatchResult {
    case ok
    case selectorMissing
    case argumentCountMismatch
    case returnTypeMismatch
    case argumentTypeMismatch
}

private final class NXHookSlot {
    let selector: Selector
    let arguments: Int
    private let lock = NSLock()
    private var saved: IMP?
    private var installed = false

    init(_ name: String, _ arguments: Int) {
        selector = NSSelectorFromString(name)
        self.arguments = arguments
    }

    var original: IMP? {
        lock.lock(); defer { lock.unlock() }
        return saved
    }

    func matchResult(_ cls: AnyClass) -> NXHookMatchResult {
        guard let method = class_getInstanceMethod(cls, selector) else { return .selectorMissing }
        guard method_getNumberOfArguments(method) == UInt32(arguments + 2) else {
            return .argumentCountMismatch
        }
        let result = method_copyReturnType(method)
        defer { free(result) }
        guard String(cString: result) == "v" else { return .returnTypeMismatch }
        for i in 0..<(arguments + 2) {
            guard let type = method_copyArgumentType(method, UInt32(i)) else {
                return .argumentTypeMismatch
            }
            defer { free(type) }
            let value = String(cString:type)
            if i == 1 {
                guard value == ":" else { return .argumentTypeMismatch }
            } else {
                guard value.hasPrefix("@") else { return .argumentTypeMismatch }
            }
        }
        return .ok
    }

    func matches(_ cls: AnyClass) -> Bool {
        if case .ok = matchResult(cls) { return true }
        return false
    }

    func install(_ cls: AnyClass, _ replacement: IMP) {
        guard Thread.isMainThread, matches(cls) else { return }
        lock.lock()
        if installed { lock.unlock(); return }
        saved = class_getInstanceMethod(cls, selector).map(method_getImplementation)
        lock.unlock()
        var previous: IMP?
        MSHookMessageEx(cls, selector, replacement, &previous)
        lock.lock()
        if let previous = previous { saved = previous }
        installed = true
        lock.unlock()
    }
}

private let nxWillAppear = NXHookSlot("presentableWillAppearAsBanner:",1)
private let nxDidAppear = NXHookSlot("presentableDidAppearAsBanner:",1)
private let nxWillDisappear = NXHookSlot("presentableWillDisappearAsBanner:withReason:",2)
private let nxDidDisappear = NXHookSlot("presentableDidDisappearAsBanner:withReason:",2)
private let nxWillNotAppear = NXHookSlot("presentableWillNotAppearAsBanner:withReason:",2)
private let nxInteraction = NXHookSlot("userInteractionWillBeginForBannerForPresentable:",1)
private let nxLongLook = NXHookSlot("longLookWillPresentForNotificationViewController:",1)
private let nxLayout = NXHookSlot("viewDidLayoutSubviews",0)

private let nxWillAppearCallback: NXObjectCallback = { owner, selector, presentable in
    NXDiagnostic.record(.callbackWillAppear)
    if Thread.isMainThread { NXBannerCoordinator.shared.willAppear(owner) }
    if let previous = nxWillAppear.original {
        unsafeBitCast(previous,to:NXObjectCallback.self)(owner,selector,presentable)
    }
    if Thread.isMainThread { NXBannerCoordinator.shared.layout(owner) }
}
private let nxDidAppearCallback: NXObjectCallback = { owner, selector, presentable in
    NXDiagnostic.record(.callbackDidAppear)
    if let previous = nxDidAppear.original {
        unsafeBitCast(previous,to:NXObjectCallback.self)(owner,selector,presentable)
    }
    if Thread.isMainThread { NXBannerCoordinator.shared.didAppear(owner) }
}
private let nxWillDisappearCallback: NXReasonCallback = { owner, selector, presentable, reason in
    NXDiagnostic.record(.callbackWillDisappear)
    if Thread.isMainThread { NXBannerCoordinator.shared.willDisappear(owner) }
    if let previous = nxWillDisappear.original {
        unsafeBitCast(previous,to:NXReasonCallback.self)(owner,selector,presentable,reason)
    }
}
private let nxDidDisappearCallback: NXReasonCallback = { owner, selector, presentable, reason in
    NXDiagnostic.record(.callbackDidDisappear)
    // Retire before native code can synchronously install a replacement for this owner.
    if Thread.isMainThread { NXBannerCoordinator.shared.retire(owner) }
    if let previous = nxDidDisappear.original {
        unsafeBitCast(previous,to:NXReasonCallback.self)(owner,selector,presentable,reason)
    }
}
private let nxWillNotAppearCallback: NXReasonCallback = { owner, selector, presentable, reason in
    NXDiagnostic.record(.callbackWillNotAppear)
    if Thread.isMainThread { NXBannerCoordinator.shared.retire(owner) }
    if let previous = nxWillNotAppear.original {
        unsafeBitCast(previous,to:NXReasonCallback.self)(owner,selector,presentable,reason)
    }
}
private let nxInteractionCallback: NXObjectCallback = { owner, selector, presentable in
    NXDiagnostic.record(.callbackInteraction)
    // Restore before native dragging/long-look takes visual ownership. Never execute an action here.
    if Thread.isMainThread { NXBannerCoordinator.shared.retire(owner) }
    if let previous = nxInteraction.original {
        unsafeBitCast(previous,to:NXObjectCallback.self)(owner,selector,presentable)
    }
}
private let nxLongLookCallback: NXObjectCallback = { owner, selector, controller in
    NXDiagnostic.record(.callbackLongLook)
    if Thread.isMainThread { NXBannerCoordinator.shared.retire(owner) }
    if let previous = nxLongLook.original {
        unsafeBitCast(previous,to:NXObjectCallback.self)(owner,selector,controller)
    }
}
private let nxLayoutCallback: NXLayoutCallback = { owner, selector in
    NXDiagnostic.record(.callbackLayout)
    if let previous = nxLayout.original {
        unsafeBitCast(previous,to:NXLayoutCallback.self)(owner,selector)
    }
    if Thread.isMainThread { NXBannerCoordinator.shared.layout(owner) }
}

private enum NXRuntime {
    static var installed = false
    static var scheduled = false
    static var diagnosticsStarted = false
    static func scheduleInstall() {
        DispatchQueue.main.async {
            guard !installed, !scheduled else { return }
            scheduled = true
            DispatchQueue.main.async {
                scheduled = false
                install()
            }
        }
    }
    static func install() {
        guard Thread.isMainThread else { return }
        if !diagnosticsStarted {
            diagnosticsStarted = true
            NXDiagnostic.begin()
        }
        guard !installed else { return }
        let cls: AnyClass
        if let springBoardClass = NSClassFromString("SBNotificationPresentableViewController") {
            cls = springBoardClass
            NXDiagnostic.record(.installClassSB)
        } else if let notificationCenterClass = NSClassFromString("NCNotificationPresentableViewController") {
            cls = notificationCenterClass
            NXDiagnostic.record(.installClassNC)
        } else {
            NXDiagnostic.record(.installClassMissing)
            return
        }
        let hooks: [(NXHookSlot,IMP,NXDiagnostic.Phase)] = [
            (nxWillAppear,unsafeBitCast(nxWillAppearCallback,to:IMP.self),.installCheckWillAppear),
            (nxDidAppear,unsafeBitCast(nxDidAppearCallback,to:IMP.self),.installCheckDidAppear),
            (nxWillDisappear,unsafeBitCast(nxWillDisappearCallback,to:IMP.self),.installCheckWillDisappear),
            (nxDidDisappear,unsafeBitCast(nxDidDisappearCallback,to:IMP.self),.installCheckDidDisappear),
            (nxWillNotAppear,unsafeBitCast(nxWillNotAppearCallback,to:IMP.self),.installCheckWillNotAppear),
            (nxInteraction,unsafeBitCast(nxInteractionCallback,to:IMP.self),.installCheckInteraction),
            (nxLongLook,unsafeBitCast(nxLongLookCallback,to:IMP.self),.installCheckLongLook),
            (nxLayout,unsafeBitCast(nxLayoutCallback,to:IMP.self),.installCheckLayout)
        ]
        for (slot, _, checkPhase) in hooks {
            NXDiagnostic.record(checkPhase)
            switch slot.matchResult(cls) {
            case .ok: break
            case .selectorMissing:
                NXDiagnostic.record(.installSelectorMissing)
                NXDiagnostic.record(.installABIMismatch)
                return
            case .argumentCountMismatch:
                NXDiagnostic.record(.installArgumentCountMismatch)
                NXDiagnostic.record(.installABIMismatch)
                return
            case .returnTypeMismatch:
                NXDiagnostic.record(.installReturnTypeMismatch)
                NXDiagnostic.record(.installABIMismatch)
                return
            case .argumentTypeMismatch:
                NXDiagnostic.record(.installArgumentTypeMismatch)
                NXDiagnostic.record(.installABIMismatch)
                return
            }
        }
        NXBannerCoordinator.shared.start()
        for (slot, replacement, _) in hooks { slot.install(cls,replacement) }
        installed = true
        NXDiagnostic.record(.installComplete)
    }
}

@_cdecl("NXStart")
public func NXStart() { NXRuntime.scheduleInstall() }

@_cdecl("NXImagesChanged")
public func NXImagesChanged() { NXRuntime.scheduleInstall() }
