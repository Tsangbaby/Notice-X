import UIKit

/// Noninteractive decoration. The native notification view/controller and gestures stay in place.
private final class NXCardShell: UIView {
    let material = UIVisualEffectView(effect: nil)
    override init(frame: CGRect) {
        super.init(frame:frame)
        isUserInteractionEnabled = false
        accessibilityElementsHidden = true
        layer.cornerCurve = .continuous
        clipsToBounds = true
        material.isUserInteractionEnabled = false
        if UIAccessibility.isReduceTransparencyEnabled {
            backgroundColor = .black
        } else {
            material.effect = UIBlurEffect(style:.systemThickMaterialDark)
            material.contentView.backgroundColor = UIColor(white:0,alpha:0.3)
        }
        addSubview(material)
    }
    required init?(coder: NSCoder) { return nil }
    override func layoutSubviews() {
        super.layoutSubviews()
        material.frame = bounds
    }
}

/// A local reveal mask/content pose owner, never a second BannerKit frame/transform animator.
final class NXCardAnimator {
    private weak var look: UIView?
    private weak var nativeMaterial: UIView?
    private weak var content: UIView?
    private weak var request: NSObject?
    private let shell = NXCardShell(frame:.zero)
    private let maskView = UIView(frame:.zero)
    private let originalMaterialHidden: Bool
    private let originalStyle: UIUserInterfaceStyle
    private let originalContentAlpha: CGFloat
    private let originalContentTransform: CGAffineTransform
    private var animators: [UIViewPropertyAnimator] = []
    private var state = NXSession()
    private var bounds: CGRect
    private var restored = false
    private let reducedMotion: Bool

    init?(parts: NXBannerParts) {
        let look = parts.look, content = parts.content
        guard look.mask == nil, content.alpha >= 0.99, content.transform == .identity else { return nil }
        self.look = look
        self.content = content
        self.nativeMaterial = parts.material
        self.request = parts.requestIdentity
        originalMaterialHidden = parts.material.isHidden
        originalStyle = look.overrideUserInterfaceStyle
        originalContentAlpha = content.alpha
        originalContentTransform = content.transform
        bounds = look.bounds
        reducedMotion = UIAccessibility.isReduceMotionEnabled
        shell.frame = bounds
        shell.autoresizingMask = [.flexibleWidth,.flexibleHeight]
        shell.layer.cornerRadius = expandedRadius
        look.insertSubview(shell,at:0)
        maskView.backgroundColor = .black
        maskView.isUserInteractionEnabled = false
        maskView.layer.cornerCurve = .continuous
        parts.material.isHidden = true
        look.overrideUserInterfaceStyle = .dark
        if !reducedMotion {
            maskView.frame = compact
            maskView.layer.cornerRadius = compact.height * 0.5
            look.mask = maskView
            content.alpha = 0
            content.transform = originalContentTransform.concatenating(
                CGAffineTransform(translationX:0,y:CGFloat(NXMotion.contentOffsetY))
                    .scaledBy(x:CGFloat(NXMotion.contentScale),y:CGFloat(NXMotion.contentScale)))
        }
    }

    private var compact: CGRect {
        let width = min(CGFloat(56),bounds.width)
        let height = min(CGFloat(22),bounds.height)
        return CGRect(x:bounds.midX-width*0.5,y:bounds.minY,width:width,height:height)
    }
    private var expandedRadius: CGFloat { min(44,min(bounds.width,bounds.height)*0.5) }

    func matches(_ parts: NXBannerParts) -> Bool {
        !restored && look === parts.look && nativeMaterial === parts.material &&
            content === parts.content && request === parts.requestIdentity &&
            shell.superview === parts.look &&
            (reducedMotion ? parts.look.mask == nil : parts.look.mask === maskView)
    }

    func open() {
        guard !restored, state.phase == .idle else { return }
        let token = state.begin(.opening)
        if reducedMotion {
            _ = state.finish(token,from:.opening,to:.visible)
            return
        }
        let shellAnimator = spring(duration:NXMotion.openDuration,damping:NXMotion.openDamping,
                                   velocity:NXMotion.openVelocity) { [weak self] in
            guard let self = self else { return }
            self.maskView.frame = self.bounds
            self.maskView.layer.cornerRadius = self.expandedRadius
        }
        let contentAnimator = spring(duration:NXMotion.contentDuration,damping:NXMotion.contentDamping) { [weak self] in
            guard let self = self else { return }
            self.content?.alpha = self.originalContentAlpha
            self.content?.transform = self.originalContentTransform
        }
        contentAnimator.addCompletion { [weak self] position in
            guard let self = self, !self.restored,
                  self.state.finish(token,from:.opening,to:.visible) else { return }
            if position != .end { self.restore(); return }
        }
        animators = [shellAnimator,contentAnimator]
        shellAnimator.startAnimation()
        contentAnimator.startAnimation(afterDelay:NXMotion.contentDelay)
    }

    func close() {
        guard !restored, state.phase != .closing else { return }
        let token = state.begin(.closing)
        captureAndStop()
        guard !reducedMotion, look?.mask === maskView else { restore(); return }
        let closing = spring(duration:NXMotion.closeDuration,damping:NXMotion.closeDamping) { [weak self] in
            guard let self = self else { return }
            self.maskView.frame = self.compact
            self.maskView.layer.cornerRadius = self.compact.height * 0.5
            self.content?.alpha = 0
            self.content?.transform = self.originalContentTransform.concatenating(
                CGAffineTransform(translationX:0,y:CGFloat(NXMotion.contentOffsetY))
                    .scaledBy(x:CGFloat(NXMotion.contentScale),y:CGFloat(NXMotion.contentScale)))
        }
        closing.addCompletion { [weak self] _ in
            guard let self = self, !self.restored,
                  self.state.finish(token,from:.closing,to:.idle) else { return }
            self.restore()
        }
        animators = [closing]
        closing.startAnimation()
    }

    func layout() {
        guard !restored, let look = look else { return }
        guard look.bounds == bounds else {
            // Native layout/rotation takes geometry ownership. End our reveal, not native layout.
            restore()
            return
        }
        shell.frame = look.bounds
    }

    func restore() {
        guard !restored else { return }
        restored = true
        state.invalidate() // Invalidate before stopping animators or touching replaceable native views.
        for animator in animators where animator.state == .active { animator.stopAnimation(true) }
        animators.removeAll()
        if let look = look, look.mask === maskView { look.mask = nil }
        if let look = look, look.overrideUserInterfaceStyle == .dark {
            look.overrideUserInterfaceStyle = originalStyle
        }
        nativeMaterial?.isHidden = originalMaterialHidden
        content?.alpha = originalContentAlpha
        content?.transform = originalContentTransform
        shell.material.effect = nil
        shell.removeFromSuperview()
    }

    private func captureAndStop() {
        let currentFrame = maskView.layer.presentation()?.frame ?? maskView.frame
        let currentRadius = maskView.layer.presentation()?.cornerRadius ?? maskView.layer.cornerRadius
        let currentAlpha = content?.layer.presentation().map { CGFloat($0.opacity) } ?? content?.alpha
        let currentTransform = content?.layer.presentation().flatMap { layer -> CGAffineTransform? in
            CATransform3DIsAffine(layer.transform) ? CATransform3DGetAffineTransform(layer.transform) : nil
        } ?? content?.transform
        for animator in animators where animator.state == .active { animator.stopAnimation(true) }
        animators.removeAll()
        maskView.frame = currentFrame
        maskView.layer.cornerRadius = currentRadius
        if let alpha = currentAlpha { content?.alpha = alpha }
        if let transform = currentTransform { content?.transform = transform }
    }

    private func spring(duration:Double,damping:Double,velocity:Double = 0,
                        animations:@escaping () -> Void) -> UIViewPropertyAnimator {
        let timing = UISpringTimingParameters(dampingRatio:CGFloat(damping),
                                              initialVelocity:CGVector(dx:CGFloat(velocity),dy:CGFloat(velocity)))
        let animator = UIViewPropertyAnimator(duration:duration,timingParameters:timing)
        animator.addAnimations(animations)
        return animator
    }
}
