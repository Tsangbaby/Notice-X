import UIKit

/// One rounded clipping shell. Native notification content is never reparented.
private final class NXCardShell: UIView {
    let material = UIVisualEffectView(effect: nil)
    let snapshotView = UIImageView(frame:.zero)

    override init(frame: CGRect) {
        super.init(frame:frame)
        isUserInteractionEnabled = false
        accessibilityElementsHidden = true
        layer.cornerCurve = .continuous
        clipsToBounds = true
        material.isUserInteractionEnabled = false
        snapshotView.isUserInteractionEnabled = false
        if UIAccessibility.isReduceTransparencyEnabled {
            backgroundColor = .black
        } else {
            material.effect = UIBlurEffect(style:.systemThickMaterialDark)
            material.contentView.backgroundColor = UIColor(white:0,alpha:0.3)
        }
        addSubview(material)
        addSubview(snapshotView)
    }
    required init?(coder: NSCoder) { return nil }
    override func layoutSubviews() {
        super.layoutSubviews()
        material.frame = bounds
        // Like Glint, content keeps its measured open width while the shell grows.
    }
}

/// Prepare invisibly during native ingress; reveal the whole shell only after it settles.
final class NXCardAnimator {
    private weak var look: UIView?
    private weak var nativeMaterial: UIView?
    private weak var content: UIView?
    private weak var request: NSObject?
    private let shell = NXCardShell(frame:.zero)
    private let originalMaterialHidden: Bool
    private let originalStyle: UIUserInterfaceStyle
    private let originalContentAlpha: CGFloat
    private var animators: [UIViewPropertyAnimator] = []
    private var state = NXSession()
    private var bounds: CGRect
    private var restored = false
    private var shellFinished = false
    private var contentFinished = false
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
        bounds = look.bounds
        reducedMotion = UIAccessibility.isReduceMotionEnabled
        UIView.performWithoutAnimation {
            shell.isHidden = true
            look.insertSubview(shell,at:0)
            parts.material.isHidden = true
            look.overrideUserInterfaceStyle = .dark
            content.alpha = 0
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
            shell.superview === parts.look && parts.look.mask == nil
    }

    func open() {
        guard !restored, state.phase == .idle else { return }
        guard let look = look, let content = content,
              look.window != nil, look.mask == nil else { restore(); return }
        bounds = look.bounds
        let admission = NXAdmission(enabled:true,unlocked:true,banner:true,
                                    onMainThread:Thread.isMainThread,attached:look.window != nil,
                                    hasForeignMask:look.mask != nil,
                                    width:Double(bounds.width),height:Double(bounds.height))
        guard admission.allowed else { restore(); return }
        let token = state.begin(.opening)
        if reducedMotion {
            UIView.performWithoutAnimation {
                shell.frame = bounds
                shell.layer.cornerRadius = expandedRadius
                shell.layoutIfNeeded()
                shell.isHidden = false
                content.alpha = originalContentAlpha
            }
            _ = state.finish(token,from:.opening,to:.visible)
            return
        }
        // The shell's local origin is zero even when the native look scrolls its bounds.
        let contentFrame = look.convert(content.bounds,from:content)
            .offsetBy(dx:-bounds.minX,dy:-bounds.minY)
        guard contentFrame.minX.isFinite, contentFrame.minY.isFinite,
              contentFrame.width.isFinite, contentFrame.height.isFinite,
              abs(contentFrame.width-content.bounds.width) < 0.5,
              abs(contentFrame.height-content.bounds.height) < 0.5,
              let image = renderContent(content,token:token),
              !restored, state.generation == token, look.bounds == bounds else {
            restore()
            return
        }
        let snapshotView = shell.snapshotView
        UIView.performWithoutAnimation {
            snapshotView.image = image
            snapshotView.frame = contentFrame
            snapshotView.alpha = 0
            snapshotView.transform = CGAffineTransform(translationX:0,y:CGFloat(NXMotion.contentOffsetY))
                .scaledBy(x:CGFloat(NXMotion.contentScale),y:CGFloat(NXMotion.contentScale))
            shell.frame = compact
            shell.layer.cornerRadius = expandedRadius
            shell.layoutIfNeeded()
            shell.isHidden = false
        }
        let shellAnimator = spring(duration:NXMotion.openDuration,damping:NXMotion.openDamping,
                                   velocity:NXMotion.openVelocity) { [weak self] in
            guard let self = self, !self.restored, self.state.generation == token else { return }
            self.shell.frame = self.bounds
            self.shell.layoutIfNeeded()
        }
        let contentAnimator = spring(duration:NXMotion.contentDuration,damping:NXMotion.contentDamping) { [weak self] in
            guard let self = self, !self.restored, self.state.generation == token else { return }
            self.shell.snapshotView.alpha = 1
            self.shell.snapshotView.transform = .identity
        }
        shellAnimator.addCompletion { [weak self] position in
            self?.completeOpening(token,position:position,shellCompleted:true)
        }
        contentAnimator.addCompletion { [weak self] position in
            self?.completeOpening(token,position:position,shellCompleted:false)
        }
        animators = [shellAnimator,contentAnimator]
        shellAnimator.startAnimation()
        contentAnimator.startAnimation(afterDelay:NXMotion.contentDelay)
    }

    private func renderContent(_ content: UIView, token: UInt64) -> UIImage? {
        let size = content.bounds.size
        let scale = look?.window?.screen.scale ?? UIScreen.main.scale
        guard size.width.isFinite, size.height.isFinite, scale.isFinite,
              size.width > 0, size.height > 0, scale > 0, scale <= 4,
              ceil(size.width*scale)*ceil(size.height*scale) <= 2_000_000 else { return nil }
        let format = UIGraphicsImageRendererFormat()
        format.scale = scale
        format.opaque = false
        format.preferredRange = .standard
        var image: UIImage?
        UIView.performWithoutAnimation {
            content.alpha = originalContentAlpha
            defer {
                if !restored, state.generation == token { content.alpha = 0 }
            }
            content.layoutIfNeeded()
            guard !restored, state.generation == token else { return }
            image = UIGraphicsImageRenderer(size:size,format:format).image { context in
                context.cgContext.translateBy(x:-content.bounds.minX,y:-content.bounds.minY)
                content.layer.render(in:context.cgContext)
            }
        }
        return image
    }

    private func completeOpening(_ token: UInt64, position: UIViewAnimatingPosition, shellCompleted: Bool) {
        guard !restored, state.generation == token, state.phase == .opening else { return }
        guard position == .end else { restore(); return }
        if shellCompleted { shellFinished = true } else { contentFinished = true }
        guard shellFinished, contentFinished,
              state.finish(token,from:.opening,to:.visible) else { return }
        // Swap at the same native geometry; notification pixels never outlive the reveal.
        UIView.performWithoutAnimation {
            content?.alpha = originalContentAlpha
            shell.snapshotView.image = nil
        }
        animators.removeAll()
    }

    func close() {
        // Native egress is authoritative; never run another reveal over its dismissal.
        restore()
    }

    func layout() {
        guard !restored, let look = look else { return }
        if state.phase == .idle {
            bounds = look.bounds // Native preparation may still change size before did-appear.
            return
        }
        guard look.bounds == bounds else { restore(); return }
        // Do not overwrite the shell's presentation/model pose while it is opening.
        if state.phase == .visible { shell.frame = bounds }
    }

    func restore() {
        guard !restored else { return }
        restored = true
        state.invalidate()
        for animator in animators where animator.state == .active { animator.stopAnimation(true) }
        animators.removeAll()
        shell.snapshotView.image = nil
        UIView.performWithoutAnimation {
            if let look = look, look.overrideUserInterfaceStyle == .dark {
                look.overrideUserInterfaceStyle = originalStyle
            }
            nativeMaterial?.isHidden = originalMaterialHidden
            if content?.alpha == 0 { content?.alpha = originalContentAlpha }
            shell.isHidden = true
            shell.material.effect = nil
            shell.removeFromSuperview()
        }
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
