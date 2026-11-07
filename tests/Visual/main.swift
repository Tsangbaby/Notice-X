import UIKit
import Darwin

// The native resolver stays outside this bounded replay; only its resolved seam is doubled.
final class NXBannerParts {
    let look: UIView
    let material: UIView
    let content: UIView
    let requestIdentity: NSObject
    init(look: UIView, material: UIView, content: UIView, request: NSObject) {
        self.look = look; self.material = material; self.content = content
        requestIdentity = request
    }
}

private var assertions = 0
private var caseName = "prepare"
private func expect(_ condition: @autoclosure () -> Bool, _ message: String) {
    assertions += 1
    guard condition() else {
        fputs("NOTICE_X_VISUAL_FAIL case=\(caseName) assertion=\(message)\n", stderr)
        exit(1)
    }
}
private func near(_ left: CGFloat, _ right: CGFloat) -> Bool { abs(left - right) < 0.000001 }
private func descendants(_ view: UIView) -> [UIView] {
    view.subviews.flatMap { [$0] + descendants($0) }
}
private func finish(_ queued: [UIViewPropertyAnimator], _ position: UIViewAnimatingPosition = .end) {
    for animator in queued { animator.replayAnimations() }
    for animator in queued { animator.replayCompletion(position) }
}
private func imageViews(_ view: UIView) -> [UIImageView] {
    descendants(view).compactMap { $0 as? UIImageView }
}

private final class Banner {
    let root = UIWindow(frame: CGRect(x: 0, y: 0, width: 600, height: 1000))
    let look: UIView
    let material: UIView
    let holder: UIView
    let content: UIView
    let target = UIView(frame: CGRect(x: 9, y: 11, width: 40, height: 25))
    let request = NSObject()
    var parts: NXBannerParts { NXBannerParts(look: look, material: material, content: content, request: request) }
    init(width: CGFloat = 390, height: CGFloat = 144) {
        look = UIView(frame: CGRect(x: 7, y: 19, width: width, height: height))
        material = UIView(frame: look.bounds)
        holder = UIView(frame: look.bounds)
        content = UIView(frame: CGRect(x: 13, y: 17, width: width - 26, height: height - 34))
        root.addSubview(look); look.addSubview(material); look.addSubview(holder)
        holder.addSubview(content); content.addSubview(target)
        look.overrideUserInterfaceStyle = .light
    }
    func shell() -> UIView {
        let owned = look.subviews.filter { $0 !== material && $0 !== holder }
        expect(owned.count == 1, "one-owned-shell")
        return owned[0]
    }
    func owner() -> NXCardAnimator {
        guard let owner = NXCardAnimator(parts: parts) else {
            expect(false, "eligible-init"); fatalError("unreachable")
        }
        return owner
    }
}

private struct NativeGeometry {
    struct Saved {
        let view: UIView
        let frame: CGRect
        let bounds: CGRect
        let transform: CGAffineTransform
        let parent: UIView?
        let children: [ObjectIdentifier]
    }
    let saved: [Saved]
    let mutationStart: Int
    init(_ banner: Banner) {
        saved = [banner.look, banner.material, banner.holder, banner.content, banner.target].map { view in
            // Preparation may already have inserted our shell. Only the two fixture-native
            // roots belong to the look's protected child order; teardown must remove the shell.
            let children = view === banner.look ? [banner.material, banner.holder] : view.subviews
            return Saved(view: view, frame: view.frame, bounds: view.bounds, transform: view.transform,
                         parent: view.superview, children: children.map(ObjectIdentifier.init))
        }
        mutationStart = VisualTrace.mutations.count
    }
    func verify(_ banner: Banner) {
        for value in saved {
            expect(value.view.frame == value.frame, "native-frame-unchanged")
            expect(value.view.bounds == value.bounds, "native-bounds-unchanged")
            expect(value.view.transform == value.transform, "native-transform-unchanged")
            expect(value.view.superview === value.parent, "native-parent-unchanged")
            // Adding our sibling shell is allowed; moving any native child is not.
            let current = value.view.subviews.map(ObjectIdentifier.init)
            expect(current.filter { value.children.contains($0) } == value.children,
                   "native-child-order-unchanged")
            if value.view !== banner.look { expect(current == value.children, "native-children-unchanged") }
        }
        let ids = Set(saved.map { ObjectIdentifier($0.view) })
        let geometryKeys: Set<String> = ["frame", "bounds", "transform", "superview", "mask"]
        expect(!VisualTrace.mutations.dropFirst(mutationStart).contains {
            ids.contains($0.view) && geometryKeys.contains($0.property)
        }, "no-native-geometry-writes-even-transiently")
        expect(banner.look.mask == nil, "no-native-mask")
    }
}

private func compact(_ bounds: CGRect) -> CGRect {
    let width = min(CGFloat(56), bounds.width), height = min(CGFloat(22), bounds.height)
    return CGRect(x: bounds.midX - width / 2, y: bounds.minY, width: width, height: height)
}
private func blurFills(_ shell: UIView) {
    let blurs = descendants(shell).compactMap { $0 as? UIVisualEffectView }
    expect(blurs.count == 1, "one-live-material")
    expect(blurs[0].frame == shell.bounds, "blur-layout-tracks-real-shell")
}
private func prepared(_ banner: Banner, _ owner: NXCardAnimator) {
    // This is deliberately the first assertion: frozen beta2 must fail behaviorally here.
    expect(banner.look.mask == nil, "no-native-mask")
    let shell = banner.shell()
    expect(shell.isHidden, "prepared-shell-hidden")
    expect(shell.clipsToBounds, "real-shell-clips")
    expect(!shell.isUserInteractionEnabled && shell.accessibilityElementsHidden, "shell-not-interactive")
    expect(banner.material.isHidden, "prepared-native-material-hidden")
    expect(banner.content.alpha == 0, "prepared-native-content-hidden")
    expect(owner.matches(banner.parts), "prepared-owner-matches")
    expect(UIViewPropertyAnimator.scheduled.isEmpty, "no-animation-before-open")
    expect(VisualTrace.renders.isEmpty && VisualTrace.liveImages == 0, "no-capture-before-open")
}
private func restored(_ banner: Banner, _ owner: NXCardAnimator) {
    expect(banner.content.alpha == 1, "restore-live-content")
    expect(!banner.material.isHidden, "restore-native-material")
    expect(banner.look.overrideUserInterfaceStyle == .light, "restore-native-style")
    expect(!owner.matches(banner.parts), "restored-owner-retired")
    expect(banner.look.subviews.count == 2, "restore-removes-owned-shell")
    expect(VisualTrace.liveImages == 0, "restore-releases-image")
}

private func testPrepare() {
    let banner = Banner()
    let before = NativeGeometry(banner)
    let owner = banner.owner()
    prepared(banner, owner)
    before.verify(banner)
    let foreign = Banner()
    expect(!owner.matches(foreign.parts), "reject-other-native-identities")
    let otherRequest = NXBannerParts(look: banner.look, material: banner.material,
                                    content: banner.content, request: NSObject())
    expect(!owner.matches(otherRequest), "reject-other-request-identity")
    owner.restore(); restored(banner, owner); before.verify(banner)
}

private func testWholeShell() {
    let banner = Banner()
    let native = NativeGeometry(banner), owner = banner.owner()
    prepared(banner, owner)
    owner.open()
    let shell = banner.shell(), queued = UIViewPropertyAnimator.scheduled
    expect(!shell.isHidden, "open-shows-shell")
    expect(shell.frame == compact(banner.look.bounds), "entry-real-shell-compact-top-centered")
    expect(near(shell.layer.cornerRadius, min(44, min(banner.look.bounds.width,
        banner.look.bounds.height) / 2)), "entry-native-radius-policy")
    blurFills(shell)
    expect(queued.count == 2, "separate-shell-and-content-animators")
    expect(near(CGFloat(queued[0].duration), CGFloat(NXMotion.openDuration)), "shell-duration")
    expect(near(CGFloat(queued[1].duration), CGFloat(NXMotion.contentDuration)), "content-duration")
    expect(near(CGFloat(queued[1].delay), CGFloat(NXMotion.contentDelay)), "content-delay")
    let timing = queued[0].timingParameters as? UISpringTimingParameters
    expect(timing != nil && near(timing!.dampingRatio, CGFloat(NXMotion.openDamping)), "shell-spring-damping")
    expect(near(timing!.initialVelocity.dy, CGFloat(NXMotion.openVelocity)), "shell-spring-velocity")
    let previews = imageViews(shell).filter { $0.image != nil }
    expect(previews.count == 1, "one-native-image-inside-shell")
    let preview = previews[0]
    weak var image = preview.image
    expect(preview.frame == banner.content.frame, "preview-keeps-final-native-content-frame")
    expect(preview.bounds.size == banner.content.bounds.size, "preview-measured-at-final-width")
    expect(preview.transform != .identity, "preview-starts-local-content-pose")
    expect(VisualTrace.renders.count == 1 && VisualTrace.liveImages == 1, "one-memory-only-image")
    expect(VisualTrace.draws.contains { $0.view == ObjectIdentifier(banner.content) &&
        $0.alpha >= 0.99 && !$0.hidden }, "capture-reads-visible-native-content")
    expect(banner.content.alpha == 0, "live-content-hidden-during-reveal")
    native.verify(banner)
    queued[0].replayAnimations()
    expect(shell.frame == banner.look.bounds, "real-shell-expands-to-look-bounds")
    expect(near(shell.layer.cornerRadius, min(44, banner.look.bounds.height / 2)), "expanded-radius")
    blurFills(shell)
    expect(preview.frame == banner.content.frame, "preview-frame-not-squashed-with-shell")
    queued[1].replayAnimations()
    expect(preview.transform == .identity, "preview-content-pose-settles")
    expect(banner.content.alpha == 0, "native-content-waits-for-completion")
    queued[0].replayCompletion(.end)
    expect(banner.content.alpha == 0 && image != nil, "one-completion-cannot-release-preview")
    queued[1].replayCompletion(.end)
    expect(banner.content.alpha == 1, "completion-restores-live-content")
    expect(image == nil && VisualTrace.liveImages == 0, "completion-releases-image")
    expect(VisualTrace.imagesCreated == 1 && VisualTrace.imagesReleased == 1, "single-capture-balanced-release")
    expect(owner.matches(banner.parts), "completed-owner-still-matches")
    owner.open(); expect(VisualTrace.renders.count == 1, "duplicate-open-does-not-recapture")
    native.verify(banner)
    let count = UIViewPropertyAnimator.scheduled.count
    owner.close(); restored(banner, owner)
    expect(UIViewPropertyAnimator.scheduled.count == count, "native-egress-no-close-animation")
    native.verify(banner)
}

private func testPendingResize() {
    let banner = Banner()
    let actual = banner.owner()
    banner.look.bounds = CGRect(x: 4, y: 3, width: 430, height: 190)
    banner.content.frame = CGRect(x: 14, y: 21, width: 402, height: 158)
    let native = NativeGeometry(banner)
    actual.layout()
    expect(actual.matches(banner.parts), "pending-resize-does-not-retire-owner")
    expect(banner.shell().isHidden && banner.content.alpha == 0, "pending-resize-remains-prepared")
    expect(VisualTrace.renders.isEmpty, "pending-resize-does-not-capture")
    actual.open()
    let shell = banner.shell()
    expect(shell.frame == compact(banner.look.bounds), "pending-resize-uses-new-compact-bounds")
    let previews = imageViews(shell).filter { $0.image != nil }
    expect(previews.count == 1 && previews[0].frame == banner.content.frame.offsetBy(
        dx: -banner.look.bounds.minX, dy: -banner.look.bounds.minY), "pending-resize-final-content-frame")
    finish(UIViewPropertyAnimator.scheduled)
    expect(shell.frame == banner.look.bounds, "pending-resize-expands-to-new-bounds")
    expect(banner.look.convert(previews[0].bounds, from: previews[0]) ==
        banner.look.convert(banner.content.bounds, from: banner.content), "snapshot-and-live-content-share-native-rectangle")
    blurFills(shell); native.verify(banner)
    actual.restore(); restored(banner, actual)
}

private func testInterruption() {
    for position in [UIViewAnimatingPosition.current, .start] {
        let banner = Banner()
        let before = NativeGeometry(banner), owner = banner.owner()
        let offset = UIViewPropertyAnimator.scheduled.count
        owner.open()
        finish(Array(UIViewPropertyAnimator.scheduled.dropFirst(offset)), position)
        restored(banner, owner); before.verify(banner)
    }
    // Content may finish first; settlement still belongs to both animators.
    do {
        let banner = Banner()
        let actual = banner.owner()
        let offset = UIViewPropertyAnimator.scheduled.count
        actual.open()
        let queued = Array(UIViewPropertyAnimator.scheduled.dropFirst(offset))
        for animator in queued { animator.replayAnimations() }
        queued[1].replayCompletion(.end)
        expect(banner.content.alpha == 0 && VisualTrace.liveImages == 1, "content-first-completion-waits-for-shell")
        queued[0].replayCompletion(.end)
        expect(banner.content.alpha == 1 && VisualTrace.liveImages == 0, "content-first-completion-releases-after-shell")
        actual.restore(); restored(banner, actual)
    }
    let banner = Banner()
    let actual = banner.owner(), before = NativeGeometry(banner)
    let offset = UIViewPropertyAnimator.scheduled.count
    actual.open()
    let queued = Array(UIViewPropertyAnimator.scheduled.dropFirst(offset))
    let scheduledCount = UIViewPropertyAnimator.scheduled.count
    actual.close(); restored(banner, actual)
    expect(UIViewPropertyAnimator.scheduled.count == scheduledCount, "interrupted-close-does-not-animate")
    expect(queued.allSatisfy { $0.stoppedWithoutFinishing == true }, "restore-stops-active-work")
    banner.content.alpha = 0.37; banner.material.isHidden = true
    banner.look.overrideUserInterfaceStyle = .unspecified
    actual.restore()
    finish(queued, .end)
    expect(banner.content.alpha == 0.37 && banner.material.isHidden, "stale-callback-preserves-new-native-alpha")
    expect(banner.look.overrideUserInterfaceStyle == .unspecified, "stale-callback-preserves-new-native-style")
    expect(VisualTrace.liveImages == 0, "stale-callback-does-not-resurrect-image")
    before.verify(banner)
}

private func testActiveResize() {
    let banner = Banner()
    let actual = banner.owner()
    actual.open()
    let old = UIViewPropertyAnimator.scheduled
    for animator in old { animator.replayAnimations() }
    banner.look.bounds = CGRect(x: 0, y: 0, width: 450, height: 160)
    banner.content.frame = CGRect(x: 13, y: 17, width: 424, height: 126)
    let native = NativeGeometry(banner)
    actual.layout(); restored(banner, actual)
    banner.content.alpha = 0.43
    finish(old)
    expect(banner.content.alpha == 0.43, "resized-owner-stale-callback-cannot-restore-alpha")
    native.verify(banner)
}

private func testStaleReplacement() {
    let banner = Banner()
    let before = NativeGeometry(banner), old = banner.owner()
    old.open()
    let stale = UIViewPropertyAnimator.scheduled
    for animator in stale { animator.replayAnimations() }
    old.restore()
    expect(VisualTrace.liveImages == 0, "old-image-released-before-replacement")
    let current = banner.owner()
    current.open()
    let fresh = Array(UIViewPropertyAnimator.scheduled.dropFirst(stale.count))
    let shell = banner.shell(), frame = shell.frame
    let image = imageViews(shell).first { $0.image != nil }!
    weak var ownedImage = image.image
    expect(fresh.count == 2 && fresh.allSatisfy { $0.state == .active }, "replacement-actively-animating")
    old.restore()
    for position in [UIViewAnimatingPosition.end, .current, .start] { finish(stale, position) }
    expect(current.matches(banner.parts), "stale-owner-cannot-retire-active-replacement")
    expect(banner.content.alpha == 0 && banner.material.isHidden, "stale-owner-cannot-unhide-active-replacement")
    expect(shell.superview === banner.look && shell.frame == frame, "stale-work-preserves-new-shell")
    expect(image.image === ownedImage && VisualTrace.liveImages == 1, "stale-work-preserves-new-image")
    before.verify(banner)
    finish(fresh)
    expect(banner.content.alpha == 1 && ownedImage == nil, "replacement-completes-and-releases")
    current.restore(); restored(banner, current); before.verify(banner)
}

private func testReducedMotion() {
    UIAccessibility.isReduceMotionEnabled = true
    let banner = Banner()
    let native = NativeGeometry(banner), owner = banner.owner()
    expect(VisualTrace.renders.isEmpty, "reduced-motion-preparation-never-captures")
    owner.open(); owner.layout()
    expect(banner.content.alpha == 1, "reduced-motion-keeps-live-content")
    expect(VisualTrace.renders.isEmpty && VisualTrace.liveImages == 0, "reduced-motion-never-captures")
    expect(UIViewPropertyAnimator.scheduled.isEmpty, "reduced-motion-does-not-animate")
    native.verify(banner)
    owner.close(); restored(banner, owner)
}

private func testPixelBudget() {
    let banner = Banner(width: 1400, height: 600)
    let before = NativeGeometry(banner), owner = banner.owner()
    owner.open()
    expect(VisualTrace.renders.count <= 1, "large-content-capture-at-most-once")
    for render in VisualTrace.renders {
        expect(render.scale.isFinite && render.scale > 0, "render-scale-valid")
        expect(render.physicalPixels <= 2_000_000, "render-capped-at-two-million-physical-pixels")
    }
    if VisualTrace.renders.isEmpty {
        expect(banner.content.alpha == 1, "over-budget-fallback-never-leaves-content-hidden")
    } else {
        expect(VisualTrace.liveImages == 1, "bounded-render-has-one-image")
        finish(UIViewPropertyAnimator.scheduled)
        expect(VisualTrace.liveImages == 0 && banner.content.alpha == 1, "bounded-render-completion-releases")
    }
    owner.restore(); before.verify(banner)
    expect(VisualTrace.liveImages == 0, "pixel-budget-case-releases-image")
}

// No fixture implementation of NXCardAnimator exists: the runner compiles the real source.
let cases: [(String, () -> Void)] = [
    ("prepare", testPrepare), ("whole-shell", testWholeShell),
    ("pending-resize", testPendingResize), ("interruption", testInterruption),
    ("active-resize", testActiveResize), ("stale-replacement", testStaleReplacement),
    ("reduced-motion", testReducedMotion), ("pixel-budget", testPixelBudget)
]
expect(cases.count == 8, "declared-case-count")
for (name, test) in cases {
    VisualTrace.reset(); caseName = name
    autoreleasepool { test() }
    expect(VisualTrace.liveImages == 0, "case-leaves-no-live-images")
}
print("NOTICE_X_VISUAL_PASS assertions=\(assertions)")
