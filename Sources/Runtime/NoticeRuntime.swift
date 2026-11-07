import Foundation
import ObjectiveC

private typealias NXObjectCallback = @convention(c) (AnyObject, Selector, AnyObject?) -> Void
private typealias NXReasonCallback = @convention(c) (AnyObject, Selector, AnyObject?, AnyObject?) -> Void
private typealias NXLayoutCallback = @convention(c) (AnyObject, Selector) -> Void

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

    func matches(_ cls: AnyClass) -> Bool {
        guard let method = class_getInstanceMethod(cls, selector),
              method_getNumberOfArguments(method) == UInt32(arguments + 2) else { return false }
        let result = method_copyReturnType(method)
        defer { free(result) }
        guard String(cString: result) == "v" else { return false }
        for i in 0..<(arguments + 2) {
            guard let type = method_copyArgumentType(method, UInt32(i)) else { return false }
            defer { free(type) }
            let value = String(cString:type)
            if i == 1 {
                guard value == ":" else { return false }
            } else {
                guard value.hasPrefix("@") else { return false }
            }
        }
        return true
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
    if Thread.isMainThread { NXBannerCoordinator.shared.willAppear(owner) }
    if let previous = nxWillAppear.original {
        unsafeBitCast(previous,to:NXObjectCallback.self)(owner,selector,presentable)
    }
    if Thread.isMainThread { NXBannerCoordinator.shared.layout(owner) }
}
private let nxDidAppearCallback: NXObjectCallback = { owner, selector, presentable in
    if let previous = nxDidAppear.original {
        unsafeBitCast(previous,to:NXObjectCallback.self)(owner,selector,presentable)
    }
    if Thread.isMainThread { NXBannerCoordinator.shared.didAppear(owner) }
}
private let nxWillDisappearCallback: NXReasonCallback = { owner, selector, presentable, reason in
    if Thread.isMainThread { NXBannerCoordinator.shared.willDisappear(owner) }
    if let previous = nxWillDisappear.original {
        unsafeBitCast(previous,to:NXReasonCallback.self)(owner,selector,presentable,reason)
    }
}
private let nxDidDisappearCallback: NXReasonCallback = { owner, selector, presentable, reason in
    if let previous = nxDidDisappear.original {
        unsafeBitCast(previous,to:NXReasonCallback.self)(owner,selector,presentable,reason)
    }
    if Thread.isMainThread { NXBannerCoordinator.shared.retire(owner) }
}
private let nxWillNotAppearCallback: NXReasonCallback = { owner, selector, presentable, reason in
    if Thread.isMainThread { NXBannerCoordinator.shared.retire(owner) }
    if let previous = nxWillNotAppear.original {
        unsafeBitCast(previous,to:NXReasonCallback.self)(owner,selector,presentable,reason)
    }
}
private let nxInteractionCallback: NXObjectCallback = { owner, selector, presentable in
    // Restore before native dragging/long-look takes visual ownership. Never execute an action here.
    if Thread.isMainThread { NXBannerCoordinator.shared.retire(owner) }
    if let previous = nxInteraction.original {
        unsafeBitCast(previous,to:NXObjectCallback.self)(owner,selector,presentable)
    }
}
private let nxLongLookCallback: NXObjectCallback = { owner, selector, controller in
    if Thread.isMainThread { NXBannerCoordinator.shared.retire(owner) }
    if let previous = nxLongLook.original {
        unsafeBitCast(previous,to:NXObjectCallback.self)(owner,selector,controller)
    }
}
private let nxLayoutCallback: NXLayoutCallback = { owner, selector in
    if let previous = nxLayout.original {
        unsafeBitCast(previous,to:NXLayoutCallback.self)(owner,selector)
    }
    if Thread.isMainThread { NXBannerCoordinator.shared.layout(owner) }
}

private enum NXRuntime {
    static var installed = false
    static var scheduled = false
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
        guard Thread.isMainThread, !installed,
              let cls = NSClassFromString("SBNotificationPresentableViewController") ??
                        NSClassFromString("NCNotificationPresentableViewController") else { return }
        let hooks: [(NXHookSlot,IMP)] = [
            (nxWillAppear,unsafeBitCast(nxWillAppearCallback,to:IMP.self)),
            (nxDidAppear,unsafeBitCast(nxDidAppearCallback,to:IMP.self)),
            (nxWillDisappear,unsafeBitCast(nxWillDisappearCallback,to:IMP.self)),
            (nxDidDisappear,unsafeBitCast(nxDidDisappearCallback,to:IMP.self)),
            (nxWillNotAppear,unsafeBitCast(nxWillNotAppearCallback,to:IMP.self)),
            (nxInteraction,unsafeBitCast(nxInteractionCallback,to:IMP.self)),
            (nxLongLook,unsafeBitCast(nxLongLookCallback,to:IMP.self)),
            (nxLayout,unsafeBitCast(nxLayoutCallback,to:IMP.self))
        ]
        guard hooks.allSatisfy({ $0.0.matches(cls) }) else { return }
        NXBannerCoordinator.shared.start()
        for (slot, replacement) in hooks { slot.install(cls,replacement) }
        installed = true
    }
}

@_cdecl("NXStart")
public func NXStart() { NXRuntime.scheduleInstall() }

@_cdecl("NXImagesChanged")
public func NXImagesChanged() { NXRuntime.scheduleInstall() }
